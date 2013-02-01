import os, datetime, random, string, urllib, math
from google.appengine.ext import webapp
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp import util
from google.appengine.dist import use_library
from google.appengine.ext import db
from google.appengine.api import users
use_library('django', '1.2')
from google.appengine.ext.webapp import template
from django.utils import simplejson
from models import *
from geo import geotypes
import braintree

template.register_template_library('django.contrib.humanize.templatetags.humanize')

BINGKEY = "AvlvQ1BWQVdLL1vAdlB8F5A11g-R5v_AbhgBIk_HYS2kje3pxB0MyUyy5YfkOCUB"

############## HELPER FUNCTIONS #####################

def get_lat_long(query):
    query = urllib.quote_plus(query)
    url ="http://dev.virtualearth.net/REST/v1/Locations?query=" + query + "&key=" + BINGKEY
    jsondata = simplejson.loads(urllib.urlopen(url).read())

    #only want one result
    if len(jsondata['resourceSets'][0]['resources']) == 1: 
        return jsondata['resourceSets'][0]['resources'][0]['point']['coordinates']
    else:
        return None

def get_lat_long_city_state_address(query):
    query = urllib.quote_plus(query)
    url ="http://dev.virtualearth.net/REST/v1/Locations?query=" + query + "&key=" + BINGKEY
    jsondata = simplejson.loads(urllib.urlopen(url).read())

    #check results exist, take first result
    if len(jsondata['resourceSets'][0]['resources']) > 0: 
        values = jsondata['resourceSets'][0]['resources'][0]['point']['coordinates']
        values.append(jsondata['resourceSets'][0]['resources'][0]['address']['locality'])  #CITY
        values.append(jsondata['resourceSets'][0]['resources'][0]['address']['adminDistrict'])  #STATE
        values.append(jsondata['resourceSets'][0]['resources'][0]['address']['addressLine']) #ADDRESS
        return values
    else:
        return None

def get_location_string(address = None, city = None, state = None, zipcode = None):
    string = ""
    if address: string = ",".join((string, address))
    if city: string = ",".join((string, city))
    if state: string = ",".join((string, state))
    if zipcode: string = ",".join((string, zipcode))
    return string

def queryfunctionfactory(min_price, max_price, min_sqft, max_sqft):
    #a list generator that will filter
    # [p for p in listings if queryfunction(p.office_sq_ft, p.price)]
    def queryfunction(price, sqft):
        if min_price:
            if price < min_price: return False
        if max_price:
            if price > max_price: return False
        if min_sqft:
            if sqft < min_sqft: return False
        if max_sqft:
            if sqft > max_sqft: return False
        return True
    return queryfunction

############## REQUEST CLASSES ######################

class AdClick(webapp.RequestHandler):
    def get(self, key):
        ad = db.get(db.Key(key))
        ad.click += 1
        ad.put()
        self.redirect(ad.link)

class LoginCheck(webapp.RequestHandler):
#check for changes to email address login and create an account if not there immediately when a user logs in
    def get(self):
        user = users.get_current_user()
        account = Account.all().filter("user =", user).get()
        #first check for email address changes
        if not account:
            account = Account.all().filter("userid =", user.user_id()).get()
            if account:
                account.user = user
                account.put()
        #second create a new account
        if not account:
            account = Account(
                user = user,
                userid = user.user_id(),
                points = 0,
                display_name = None,
                phone = "",
                company = "",
                description = "",
                )
            account.put()
        if not account.points:
            account.points = 0
            account.put()
        self.redirect('/panel')

class MainPage(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        values = {'inhomesection': True,
                  'user': user,
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'account': Account.all().filter("user =", user).get(),
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/index.html')
        self.response.out.write(template.render(path, values))

class Search(webapp.RequestHandler):
    #filtered search results
    def get(self):
        #check to see if search data was passed
        if not self.request.get('page'):
            listings = Listing.all().filter('active =', 'on').order('-date_created').fetch(20)
            user = users.get_current_user()
            values = {'insearchsection': True, 
                      'listings': listings,
                      'user': user,
                      'login_url': users.create_login_url('/logincheck'),
                      'logout_url': users.create_logout_url('/'),
                      'page': '1',
                      'numberofpages': '1',
                      'radius': '10', #starting value
                      'bingkey': BINGKEY,
                      'searchtype': 'Table',
                      'account': Account.all().filter("user =", user).get(),
                      }
            path = os.path.join(os.path.dirname(__file__), '_templates/search.html')
            self.response.out.write(template.render(path, values))            
            return

        page = int(self.request.get('page'))
        numberofresults = 20
        location = self.request.get('location')
        min_price = self.request.get('min_price')
        max_price = self.request.get('max_price')
        min_sqft = self.request.get('min_sqft')
        max_sqft = self.request.get('max_sqft')
        radius = self.request.get('radius')
        if location == "" or location == "Address": location = None
        if min_price == "min price": min_price = None
        if max_price == "max price": max_price = None
        if min_sqft == "min sqft.": min_sqft = None
        if max_sqft == "max sqft.": max_sqft = None        
        sale_type = self.request.get('sale_type')
        
        listing_type = []
        if self.request.get('commercial') == 'on': listing_type.append('commercial')
        if self.request.get('industrial') == 'on': listing_type.append('industrial')
        if self.request.get('office') == 'on': listing_type.append('office')
        if self.request.get('apartment') == 'on': listing_type.append('apartment')
        if self.request.get('land') == 'on': listing_type.append('land')
        
        offset = numberofresults * (page - 1)
        listings = Listing.all().filter('active =', 'on')
        if sale_type and sale_type != "B":
            listings.filter('sale_type =', sale_type)
        if listing_type:
            listings.filter('listing_type IN', listing_type)
        if location:
            latlong = get_lat_long(location)
            if latlong:
                listings = Listing.proximity_fetch(listings, geotypes.Point(latlong[0], latlong[1]), max_results = 100, max_distance = (1609 * int(radius)))
            else:
                listings.fetch(100)
                #location not found, error message?
        else:
            listings.fetch(100)
            latlong = None

        tempfunction = queryfunctionfactory(min_price, max_price, min_sqft, max_sqft)

        listings = [l for l in listings if tempfunction(l.price, l.sq_ft)]

        listings = listings[offset:(offset+numberofresults)]

        numberofpages = int(math.ceil(len(listings) / numberofresults))
        if not numberofpages: numberofpages = 1
        
        searchtype = self.request.get("searchtype")
        if not searchtype:
            searchtype = self.request.get("lastsearchtype")

        user = users.get_current_user()
        
        criteria = {
            'location': location,
            'min_price': min_price,
            'max_price': max_price,
            'min_sqft': min_sqft,
            'max_sqft': max_sqft,
            'sale_type': sale_type,
            'listing_type': listing_type,
            }
        values = {
            'insearchsection':True, 
            'listings': listings,
            'user': user,
            'logout_url': users.create_logout_url('/'),
            'login_url': users.create_login_url('/logincheck'),
            'account': Account.all().filter("user =", user).get(),
            'page': str(page),
            'numberofpages': numberofpages,
            'radius': radius,
            'bingkey': BINGKEY,
            'latlong': latlong,
            'criteria': criteria,
            'searchtype': searchtype,
            }
        
        if searchtype == "Map":
            path = os.path.join(os.path.dirname(__file__), '_templates/mapsearch.html')
        elif searchtype == "Table":
            path = os.path.join(os.path.dirname(__file__), '_templates/tablesearch.html')
        elif searchtype == "Tiles":
            path = os.path.join(os.path.dirname(__file__), '_templates/tilesearch.html')
        else:
            path = os.path.join(os.path.dirname(__file__), '_templates/search.html')            
        self.response.out.write(template.render(path, values))
        
class ListingPage(webapp.RequestHandler):
    def get(self,  id):
        try: listing = Listing.get_by_id(int(id))
        except:
            self.redirect('/')
            return
        listing.views += 1
        listing.put()
        #fetch an ad in the same city as the listing
        '''ads = Advertisement.all().run()
        if len(ads) > 1:
            ads = [a for a in ads if listing.city in ads.cities]
            ad  = ads[int(random.random()*len(ads))]
        else:
            ad = None'''
        ad = None
        suites = Suite.all().filter('listing =', listing).run()
        user = users.get_current_user()
        owner = Account.all().filter('user =', listing.owner).get()
        values = {'insearchsection': True,
                  'listing': listing,
                  'suites': suites,
                  'ad': ad,
                  'user': user,
                  'owner': owner,
                  'account': Account.all().filter("user =", user).get(),
                  'is_admin': users.is_current_user_admin(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'bingkey': BINGKEY,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/listing.html')
        self.response.out.write(template.render(path, values))

class About(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'inaboutsection': True,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/about.html')
        self.response.out.write(template.render(path, values))

class Panel(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel.html')
        self.response.out.write(template.render(path, values))

class PanelAccount(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        account = Account.all().filter("user = ", user).get()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'account': account,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_account.html')
        self.response.out.write(template.render(path, values))

class PanelAccountEdit(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        account = Account.all().filter('user =', user).get()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/account/upload'),
                  'account': account,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_account_edit.html')
        self.response.out.write(template.render(path, values))

class PanelAccountUpload(blobstore_handlers.BlobstoreUploadHandler):
    def post(self, key=None):
        try: blob_info = self.get_uploads()[0]
        except:
            blob_info = None
            
        if not users.get_current_user():
            blob_info.delete()
            self.redirect(users.create_login_url('/logincheck'))
            return

        if self.request.get('action') == 'edit':
            account = Account.all().filter("user =", users.get_current_user()).get()
        elif self.request.get('action') == 'create':
            account = Account(user = users.get_current_user(), points = 0, level = 'basic')
            
        if blob_info:
            if account.picture:
                blobstore.delete([account.picture.picture.key()])
                account.picture.delete()
            try:
                picture_data = Picture(picture = blob_info.key())
                picture_data.put()
            except NotImageError:
                picture_data = None
        else:
            picture_data = None
            
        account.first_name = self.request.get('first_name')
        account.last_name = self.request.get('last_name')
        account.display_name = self.request.get('display_name')
        account.phone = self.request.get('phone')
        account.company = self.request.get('company')
        account.description = self.request.get('description')
        account.role = self.request.get('role')
        if picture_data: account.picture = picture_data

        account.put()

        self.redirect('/panel/account')

class PanelAdvertise(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        advertisements = Advertisement.all().filter("owner =", user).run()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'advertisements': advertisements,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_advertise.html')
        self.response.out.write(template.render(path, values))

    def post(self):
        action = self.request.get('action')
        if action == 'delete':
            ad = db.get(db.Key(self.request.get('key')))
            if ad.picture: 
                blobstore.delete([ad.picture.picture.key()])
                ad.picture.delete()
            ad.delete()

        self.redirect('/panel/advertise')

class PanelAdvertisementUpload(blobstore_handlers.BlobstoreUploadHandler):
    def get(self, key=None):
        if key:
            advertisement = db.get(db.Key(key))
            editing = True
        else:
            advertisement = None
            editing = False
        listing = None
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'editing': editing,
                  'advertisement': advertisement,
                  'upload_url': blobstore.create_upload_url('/panel/advertisement/upload')
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_advertisement_edit.html')
        self.response.out.write(template.render(path, values))

    def post(self):
        user = users.get_current_user()
        if self.request.get('action') == "edit":
            ad = db.get(db.Key(self.request.get('key')))
        else:
            ad = Advertisement(owner = user, clicks = 0, views = 0, active = False)

        try: blob_info = self.get_uploads()[0]
        except: blob_info = None
        if not user:
            blob_info.delete()
            self.redirect(users.create_login_url('/logincheck'))
            return
        
        if blob_info:
            if ad.picture:
                blobstore.delete([ad.picture.picture.key()])
                ad.picture.delete()
            try:
                picture_data = Picture(picture = blob_info.key())
                picture_data.put()
            except NotImageError:
                picture_data = None
        else:
            picture_data = None

        ad.title = self.request.get('title')
#        ad.cities same name in different states...  needs to be zip code based.
        ad.location = self.request.get('location')
#        ad.sites HMMM.
        if picture_data: ad.picture = picture_data
        ad.link = self.request.get('link')
        ad.link_to_picture = self.request.get('link_to_picture')
        ad.start_date = self.request.get('start_date')
        ad.end_date = self.request.get('end_date')
        ad.radius = self.request.get('radius')
        ad.description = self.request.get('description')
#        ad.cost
#        ad.views
#        ad.clicks
        
        ad.put()
        
        advertisements = Advertisement.all().filter("user =", user).get()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'advertisements': advertisements,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_advertise.html')
        self.response.out.write(template.render(path, values))        

class PanelAdvertisementActivate(webapp.RequestHandler):
    def get(self, key):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        #determine cost of the advertisement and serve an accept charge page
        ad = db.get(db.Key(key))
        
        if not ad or ad.active:
            self.redirect('/panel/advertise')


            '''Cost formula... something like
            1 + (radius of coverage * 1) + (adfrequency * 1) + (duration * 1) 
            '''
        ad.cost = 55
        ad.put()

        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'ad': ad,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_advertisement_activate.html')
        self.response.out.write(template.render(path, values))
    
    def post(self, key):
        #set advertisement as activated, process a purchase on the account, redirect to ad listings
        try: ad = db.get(db.Key(key))
        except:
            self.redirect('/panel/advertise')
            return
        account = Account.all().filter("user =", ad.owner).get()

        if self.request.get('action') == 'Cancel':
            self.redirect('/panel/advertise')
            return
        
        ad.active = True
        ad.put()
        
        account.points -= ad.cost
        account.put()
        
        purchase = Purchase(title = "Activated advertisement",
                            points = ad.cost,
                            description = ad.title,
                            account = account
                            )
        purchase.put()
        self.redirect('/panel/advertise')

class PanelListingList(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'sale': Listing.all().filter('owner =', user).filter('sale_type =', 'S').run(),
                  'lease': Listing.all().filter('owner =', user).filter('sale_type =', 'L').run(),
                  'both': Listing.all().filter('owner =', user).filter('sale_type =', 'B').run(),
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_listing_list.html')
        self.response.out.write(template.render(path, values))

    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        listing = db.get(db.Key(self.request.get("key")))
        if self.request.get('action') == 'show':
            listing.active = "on"
            listing.put()
        elif self.request.get('action') == 'hide':
            listing.active = ""
            listing.put()
        elif self.request.get('action') == 'delete':
            if listing.picture_set:
                for picture in listing.picture_set:
                    blobstore.delete(picture.picture.key())
                    picture.delete()
            if listing.brochure:
                blobstore.delete(listing.brochure.key())
            if listing.suite_set:
                for suite in listing.suite_set:
                    if suite.floorplan:
                        blobstore.delete(suite.floorplan.key())
                    suite.delete()
            listing.active = ""
            listing.owner = None
            listing.put()  #save the data for our records.
        elif self.request.get('action') == 'upgrade':
            pass

        self.redirect('/panel/listing')

class PanelListingCreate(webapp.RequestHandler):
    def get(self):
        listing = None
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'listing': listing,
                  'editing': False,
                  'upload_url': blobstore.create_upload_url('/panel/listing/upload')
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_listing_edit.html')
        self.response.out.write(template.render(path, values))

class PanelListingEdit(webapp.RequestHandler):
    def get(self, key=None):
        try: listing = db.get(db.Key(key))
        except:
            pass
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        editing = True
        if key == None:
            listing = None
            editing = False
        if editing and not listing.owner == user:
            self.redirect('/')
            return

        if self.request.get('action') == 'delete-suite':
            suite = db.get(db.Key(self.request.get('suitekey')))
            blobstore.delete(suite.floorplan.key())
            suite.delete()

        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/listing/upload'),
                  'listing': listing,
                  'editing': editing,
                  'type': listing.sale_type,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_listing_edit.html')
        self.response.out.write(template.render(path, values))

class PanelListingUpload(blobstore_handlers.BlobstoreUploadHandler):
    def post(self, key=None):
        try: blob_info = self.get_uploads()[0]
        except:
            blob_info = None
            
        user = users.get_current_user()

        if not user:
            blob_info.delete()
            self.redirect(users.create_login_url('/logincheck'))
            return

        if self.request.get('key'):
            listing = db.get(db.Key(self.request.get('key')))
            if not listing.owner == user:
                blob_info.delete()
                return
        else:
            listing = Listing()
            listing.owner = user            
            listing.views = 0

        if self.request.get('brochure_remove') == 'on':
            blobstore.delete(listing.brochure.key())
            listing.brochure = None
        
        if blob_info:
            if 'pdf' in blob_info.content_type: 
                listing.brochure = blob_info.key()
            else: blob_info.delete()

        listing.title = self.request.get('title')
        listing.sale_type = self.request.get('sale_type')
        listing.listing_type = self.request.get('listing_type')
        listing.address = self.request.get('address')
        #listing.city = self.request.get('city')
        #listing.state = self.request.get('state')
        listing.zip_code = self.request.get('zip_code')
        listing.sq_ft = self.request.get('sq_ft')
        listing.land_acres = self.request.get('land_acres')
        listing.price = self.request.get('price')
        listing.units = self.request.get('units')
        listing.stories = self.request.get('stories')
        listing.hvac = self.request.get('hvac')
        listing.elevator = self.request.get('elevator')
        listing.parcel_number = self.request.get('parcel_number')
        listing.office_sq_feet = self.request.get('office_sq_feet')
        listing.warehouse_sq_feet = self.request.get('warehouse_sq_feet')
        listing.features = [str(feature).strip() for feature in self.request.get('features').split('\r')]
        listing.description = self.request.get('description')
        listing.active = self.request.get('active')
        #listing.sites =  ###done elsewhere? special features/upgrades page?
        #listing.type = "simple" #simple until they have paid some $$ to increase
        location = get_location_string(address = listing.address, zipcode = listing.zip_code)
        latlongcitystate = get_lat_long_city_state_address(location)
        if latlongcitystate: 
            listing.location = db.GeoPt(latlongcitystate[0], latlongcitystate[1])
            listing.city = latlongcitystate[2]
            listing.state = latlongcitystate[3]
            listing.address = latlongcitystate[4]
            listing.update_location()
        else:
            #not specific on location, send a message?
            pass
        listing.put()
        
        self.redirect('/panel/listing')

class PanelAccountUpgrade(webapp.RequestHandler):
    pass

class PanelAccountAddpoints(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'referer': self.request.headers['Referer'],
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_account_addpoints.html')
        self.response.out.write(template.render(path, values))        

    def post(self):
        #process the payment using whatever gateway.
        if self.request.get('amount') == 'custom':
            amount = self.request.get('customvalue')
        else:
            amount = self.request.get('amount')
        payment = True
        #add points to account and return to referer
        if payment:
            user = users.get_current_user()
            account = Account.all().filter("user =", user).get()
            account.points += int(amount)
            account.put()
            self.redirect(self.request.get('referer'))
        else:
            pass

class PanelListingUpgrade(webapp.RequestHandler):
    def get(self, key):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        #pulls up the listing upgrade page for a listing
        listing = db.get(db.Key(key))
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'listing': listing,
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/suite/upload'),
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_listing_upgrades.html')
        self.response.out.write(template.render(path, values))        
    def post(self):
        #posts a form that has a myriad of upgrades
        pass

class PanelListingGallery(webapp.RequestHandler):
    def get(self, key):
        try: listing = db.get(db.Key(key))
        except:
            pass
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        if not listing.owner == user:
            self.redirect('/panel/listing')
            return

        user = users.get_current_user()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/listing/gallery/upload'),
                  'listing': listing,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_listing_gallery.html')
        self.response.out.write(template.render(path, values))

    def post(self, key):
        try: picture = db.get(db.Key(self.request.get('key')))
        except:
           pass
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return

        '''        if not picture.listing.owner == user:
            self.redirect('/panel/listing')
            return'''

        if self.request.get('action') == "show":
            picture.visible = True
            picture.put()

        if self.request.get('action') == "hide":
            picture.visible = False
            picture.put()

        if self.request.get('action') == "move-up" or self.request.get('action') == "move-down":
            if self.request.get('action') == "move-up":
                change = -1
            else:   #move picture down the list
                change = 1
            #get the desired location and picture
            desired = picture.order + change
            relocatedpicture = Picture.all().filter("listing =", picture.listing).filter("order =", desired).get()
            #swap the two
            relocatedpicture.order = picture.order
            picture.order = desired
            relocatedpicture.put()
            picture.put()


        if self.request.get('action') == "delete":
            blobstore.delete([picture.picture.key()])
            picture.delete()
            gallery = Picture.all().filter("listing =", picture.listing).order("order").run()
            i = 0
            for picture in gallery:
                picture.order = i
                picture.put()
                i+=1

        if self.request.get('action') == "edit":
            picture.description = self.request.get('description')
            picture.put()

        if self.request.get('action') == "set_default":
            lastdefault = Picture.all().filter("listing =", picture.listing).filter("display_picture =", True).get()
            lastdefault.display_picture = False
            lastdefault.put()
            picture.display_picture = True
            picture.put()
                        
        self.redirect('/panel/listing/gallery/' + str(picture.listing.key()))
       
class PanelListingGalleryUpload(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        try: blob_info = self.get_uploads()[0]
        except:
            blob_info = None
        if not users.get_current_user():
            blob_info.delete()
            self.redirect(users.create_login_url('/logincheck'))
            return

        listing = db.get(db.Key(self.request.get('key')))
        picture = Picture()
        picture.listing = listing
        try: picture.picture = blob_info
        except NotImageError:
            blob_info.delete()
            self.redirect('/')
            return
        picture.order = listing.picture_set.count()
        picture.visible = True
        picture.description = self.request.get('description')

        if listing.picture_set.count() == 0:
            picture.picture = True

        picture.put()

        self.redirect('/panel/listing/gallery/' + str(listing.key()))

class PanelSuiteCreate(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        listing = db.get(db.Key(self.request.get('key')))
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/suite/upload'),
                  'listing': listing,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_suite_create.html')
        self.response.out.write(template.render(path, values))

class PanelSuiteEdit(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        listing = db.get(db.Key(self.request.get('key')))
        suite = db.get(db.Key(self.request.get('suitekey')))
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': Account.all().filter("user =", user).get(),
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/suite/upload'),
                  'listing': listing,
                  'suite': suite,
                  'editing': True,
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_suite_create.html')
        self.response.out.write(template.render(path, values))

class PanelSuiteUpload(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        listing = db.get(db.Key(self.request.get('key')))
        if self.request.get('suitekey'):
            suite = db.get(db.Key(self.request.get('suitekey')))
        else:
            suite = Suite(listing = listing)
            
        try: blob_info = self.get_uploads()[0]
        except:
            blob_info = None

        if not users.get_current_user():
            blob_info.delete()
            self.redirect(users.create_login_url())
            return

        if self.request.get('floorplan_remove') == 'on':
            blobstore.delete(suite.floorplan.key())
            suite.floorplan = None

        suite.suite_number = self.request.get('suite_number')
        suite.square_feet = self.request.get('square_feet')
        suite.price = self.request.get('price')
        suite.price_per_foot = self.request.get('price_per_foot')
        suite.hvac = self.request.get('hvac')
        suite.number_of_offices = self.request.get('number_of_offices')
        suite.windowed_offices = self.request.get('windowed_offices')
        suite.restrooms = self.request.get('restrooms')
        suite.available_immediately = self.request.get('available_immediately')
        suite.features = [str(feature).strip() for feature in self.request.get('features').split('\r')] 
        suite.walkthrough = self.request.get('walkthrough')
        if blob_info: suite.floorplan = blob_info.key()
        #suite.floorplan_type = 

        suite.put()

        self.redirect('/panel/listing/' + str(listing.key()))

class PanelPurchases(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url('/logincheck'))
            return
        account = Account.all().filter("user = ", user).get()
        purchases = Purchase.all().filter("account = ", account).run()
        values = {'user': user,
                  'is_admin': users.is_current_user_admin(),
                  'account': account,
                  'purchases': purchases,
                  'login_url': users.create_login_url('/logincheck'),
                  'logout_url': users.create_logout_url('/'),
                  'upload_url': blobstore.create_upload_url('/panel/suite/upload'),
                  }
        path = os.path.join(os.path.dirname(__file__), '_templates/panel_purchase.html')
        self.response.out.write(template.render(path, values))        

class ServeBlob(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, blobkey):
        #resource = str(urllib.unquote(blobkey))   Only used if blob is not a key
        blob_info = blobstore.BlobInfo.get(blobkey)
        self.send_blob(blob_info)
                                                
                
class GetSearch(webapp.RequestHandler):
    def get(self):
        values = []
        path = os.path.join(os.path.dirname(__file__), '_templates/satellitemain.html')
        self.response.out.write(template.render(path, values))        

    def post(self):
        values = []
        path = os.path.join(os.path.dirname(__file__), '_templates/satellitesearch.html')
        self.response.out.write(template.render(path, values))        

class GetListing(webapp.RequestHandler):
    def get(self):
        values = []
        path = os.path.join(os.path.dirname(__file__), '_templates/satellitelisting.html')
        self.response.out.write(template.render(path, values))        


################## MAIN ###################

def main():
    application = webapp.WSGIApplication([
            (r'/adc/(.*)', AdClick),
            ('/logincheck', LoginCheck),
            ('/search', Search),
            (r'/listing/(.*)', ListingPage),
            ('/about', About),
            ('/panel/account/edit', PanelAccountEdit),
            ('/panel/account/upload', PanelAccountUpload),
            ('/panel/account/upgrade', PanelAccountUpgrade),
            ('/panel/account/addpoints', PanelAccountAddpoints),
            ('/panel/account', PanelAccount),
            ('/panel/advertisement/create', PanelAdvertisementUpload),
            ('/panel/advertisement/upload', PanelAdvertisementUpload),
            (r'/panel/advertisement/activate/(.*)', PanelAdvertisementActivate),
            (r'/panel/advertisement/(.*)', PanelAdvertisementUpload),
            ('/panel/advertise', PanelAdvertise),
            ('/panel/listing/create', PanelListingCreate),
            ('/panel/listing/upload', PanelListingUpload),
            ('/panel/listing/gallery/upload', PanelListingGalleryUpload),
            (r'/panel/listing/gallery/(.*)', PanelListingGallery),
            (r'/panel/listing/upgrade/(.*)', PanelListingUpgrade),
            (r'/panel/listing/(.*)', PanelListingEdit),
            ('/panel/listing', PanelListingList),
            ('/panel/suite/edit', PanelSuiteEdit),
            ('/panel/suite/create', PanelSuiteCreate),
            ('/panel/suite/upload', PanelSuiteUpload),
            ('/panel/purchases', PanelPurchases),
            ('/panel', Panel),
            (r'/download/(.*)', ServeBlob),
            ('/getsearch', GetSearch),
            ('/getlisting', GetListing),
            ('/', MainPage),
            ],debug=True)

    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()

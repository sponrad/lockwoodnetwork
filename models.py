from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.api.images import get_serving_url
from geo.geomodel import GeoModel

class Satellite(db.Model):
    title = db.StringProperty(required = True)
    url = db.StringProperty(required = True)
    areas = db.StringListProperty() #tags of all of the areas that this site covers

class Listing(GeoModel):
    uri = db.StringProperty(required = False)
    owner = db.UserProperty()
    title = db.StringProperty(required = False)
    sale_type = db.StringProperty()  #sale, lease, both
    listing_type = db.StringProperty() #retail, industrial, office etc.
    address = db.StringProperty(required = False)
    #location = db.GeoPtProperty()    #included in GeoModel
    city = db.StringProperty(required = False)
    state = db.StringProperty(required = False)
    zip_code = db.StringProperty(required = False)
    sq_ft = db.StringProperty()
    building_sq_footage = db.StringProperty()
    office_sq_feet = db.StringProperty(required = False)
    warehouse_sq_feet =db.StringProperty(required = False)
    land_acres = db.StringProperty()
    price = db.StringProperty()
    year_built = db.StringProperty()
    brochure = blobstore.BlobReferenceProperty()
    units = db.StringProperty(required = False)
    stories = db.StringProperty(required = False)
    hvac = db.StringProperty(required = False)
    elevator = db.StringProperty(required = False)
    parcel_number = db.StringProperty(required = False)
    features = db.StringListProperty()
    description = db.TextProperty()
    active = db.StringProperty(required = False)  # set as "on" if active
    satellites = db.ListProperty(db.Key)   #contains key values of the satellites that this listing should be listed on.
    paid = db.StringListProperty()
    views = db.IntegerProperty(required = False)
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)

    def display_picture(self):
        picture = Picture.all().filter("listing =", self).filter("display_picture =", True).get()
        if not picture:
            picture = Picture.all().filter("listing =", self).filter("order =", 1).get()
        return picture
    
class Suite(db.Model):
    listing = db.ReferenceProperty(Listing)
    suite_number = db.StringProperty(required = False)
    square_feet = db.StringProperty(required = False)
    price = db.StringProperty(required = False)
    price_per_foot = db.StringProperty(required = False)
    hvac = db.StringProperty(required = False)
    number_of_offices = db.StringProperty(required = False)
    windowed_offices = db.StringProperty(required = False)
    restrooms = db.StringProperty(required = False)
    available_immediately = db.StringProperty(required = False)
    features = db.StringListProperty()
    walkthrough = db.StringProperty(required = False)
    floorplan = blobstore.BlobReferenceProperty()
    floorplan_type = db.StringProperty(required = False)
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)

class Picture(db.Model):
    listing = db.ReferenceProperty(Listing)
    suite = db.ReferenceProperty(Suite)
    title = db.StringProperty(required = False)
    visible = db.BooleanProperty()
    description = db.StringProperty(required = False)
    picture = blobstore.BlobReferenceProperty()
    order = db.IntegerProperty(required = False)
    display_picture = db.BooleanProperty()
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)

    def serve_picture(self):
        url = get_serving_url(self.picture.key())
        return url

    def serve_medium(self):
        size = 250
        url = get_serving_url(self.picture.key(), size)
        return url

    def serve_thumbnail(self):
        size = 80
        url = get_serving_url(self.picture.key(), size)
        return url

class Account(db.Model):
    #user has "listing_set" from reference ## dont think it will work.
    user = db.UserProperty()
    userid = db.StringProperty()
    role = db.StringProperty()
    first_name = db.StringProperty()
    last_name = db.StringProperty()
    display_name = db.StringProperty()
    phone = db.StringProperty()
    company = db.StringProperty()
    description = db.StringProperty(multiline = True)
    picture = db.ReferenceProperty(Picture)
    email = db.StringProperty()    #only present if a user has opted to receive email at another email address than their login address
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)
    points = db.IntegerProperty()
    level = db.StringProperty() #basic,advanced, super-cool etc.
    companypicture = db.StringProperty() #store the key value of the company pic
    website = db.StringProperty()

    def totalspent(self):
        purchases = Purchase.all().filter("account =", self)
        totalspent = 0
        for i in purchases: totalspent += i.points
        return totalspent

class Broker(db.Model):
    user = db.UserProperty()
    display_name = db.StringProperty()
    account = db.ReferenceProperty(Account)
    listing = db.ReferenceProperty(Listing)
    email = db.StringProperty()
    phone = db.StringProperty()
    picture = db.ReferenceProperty(Picture)

class Advertisement(db.Model): #or GeoModel? for location searches
    title = db.StringProperty()
    cities = db.StringListProperty()   #ad cities OR zip codes to this
    location = db.StringProperty()
    sites = db.StringListProperty()
    picture = db.ReferenceProperty(Picture)
    link = db.StringProperty()
    link_to_picture = db.StringProperty()
    start_date = db.DateTimeProperty()
    end_date = db.DateTimeProperty()
    duration = db.StringProperty()
    description = db.StringProperty()
    owner = db.UserProperty()
    cost = db.IntegerProperty()
    views = db.IntegerProperty()
    clicks = db.IntegerProperty()
    active = db.BooleanProperty()
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)

class Purchase(db.Model):
    title = db.StringProperty()
    points = db.IntegerProperty()
    description = db.StringProperty()
    date_created = db.DateTimeProperty(auto_now_add = True)
    date_edited = db.DateTimeProperty(auto_now = True)
    account = db.ReferenceProperty(Account)

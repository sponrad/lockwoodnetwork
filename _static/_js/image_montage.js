var image_montage = {
	delay : 4000,
	index : -1,
	front : '#image_layer_2',
	image_list : new Array (),
	setIndex : function () {
		this.index++;
		if (this.index == this.image_list.length)
			this.index = 0;
	},
	setNext : function () {
		this.setIndex();
		$(this.front).fadeOut('slow',function(){
			$(this).css('z-index','0').css('background-image','url('+image_montage.image_list[image_montage.index]+')');
			if (image_montage.front == '#image_layer_2')
				image_montage.front = '#image_layer_1';
			else 
				image_montage.front = '#image_layer_2';
			$(image_montage.front).css('z-index','1');
			$(this).css({'opacity':'1','display':'block'});
		});

	},
	init : function () {
		this.index = Math.floor(Math.random()*this.image_list.length) - 1;
		this.setIndex();
		$('#image_layer_2').css('background-image','url('+this.image_list[this.index]+')');
		this.setIndex();
		$('#image_layer_1').css('background-image','url('+this.image_list[this.index]+')');
		var interval = setInterval("image_montage.setNext()",this.delay);
	}
}
image_montage.image_list = imagelist;

if (imagelist.length > 0) {
	$('#image_montage_container').prepend('<div id="image_layer_1"></div><div id="image_layer_2"></div>');
	$('div.lockwood_colors_text').clone(true).appendTo($('#image_layer_1, #image_layer_2'));
	image_montage.init();
}
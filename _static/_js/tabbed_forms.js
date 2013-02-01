var tabbed_forms = {
	init: function () {
		$('div.tabbed_form_container').each(function () {
			var firstTab = $('ul.tab_list:first',this);
			$('ul.tab_list',this).not(firstTab).each(function () {
				$('li',this).removeClass('selected_tab').appendTo(firstTab);
				$(this).remove();
			});
			$('li',firstTab).each(function () {
				if (!$(this).hasClass("selected_tab")) {
					$('#'+$(this).attr('id')+'_block').hide();
				}
				$('a',this).click(function (e) {
					e.preventDefault();
					$('#'+$('li.selected_tab',$(this).parent().parent()).removeClass("selected_tab").attr('id')+'_block').hide();
					$('#'+$(this).blur().parent().addClass("selected_tab").attr('id')+'_block').show();
				});
			});
		});
	}
}

$(document).ready(function () {
	tabbed_forms.init();
});
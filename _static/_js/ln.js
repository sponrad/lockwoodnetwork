$(document).ready(function(){
    $("form").submit(function() {
	$(this).submit(function() {
            return false;
	});
	return true;
    });
});
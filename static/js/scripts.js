/* recipe slideshow */
function genShow() {
 
	var dur = 1000;
	var pDur = 5000;
 
	$('.carousel').carouFredSel({
		items: {
			visible: 1,
			width: 410,
			height: 230
		},
		prev: {
			button: "#recipeleft",
			key: "left",
			fx: "none",
			onBefore: function( data ) {
				animate( data.items.visible, pDur + ( dur * 3 ) );
				$(".carousel").css({left:0});
			},
			onAfter: function(data) {
				$("#recipetitle div:first-child").text($('.carousel div:first-child').attr('title'));
				$("#recipetitle .subtitle").text(recipeSubtitle($('.carousel div:first-child').attr('name')));
				data.items.old.find( 'img' ).stop().css({
					width: 410,
					height: 230,
					marginTop: 0,
					marginLeft: 0
				});
			}
		},
		next: {
			button: "#reciperight",
			key: "right",
			fx: "none",
			onBefore: function( data ) {
				animate( data.items.visible, pDur + ( dur * 3 ) );
				$(".carousel").css({left:0});
			},
			onAfter: function(data) {
				$("#recipetitle div:first-child").text($('.carousel div:first-child').attr('title'));
				$("#recipetitle .subtitle").text(recipeSubtitle($('.carousel div:first-child').attr('name')));
				data.items.old.find( 'img' ).stop().css({
					width: 410,
					height: 230,
					marginTop: 0,
					marginLeft: 0
				});
			}
		},
		scroll: {
			fx: 'fade',
			easing: 'linear',
			duration: dur,
			timeoutDuration: pDur,
			onBefore: function( data ) {
				animate( data.items.visible, pDur + ( dur * 3 ) );
				$("#recipetitle").fadeOut();
				$(".carousel").css({left:0});
			},
			onAfter: function( data ) {
				$("#recipetitle div:first-child").text($('.carousel div:first-child').attr('title'));
				$("#recipetitle .subtitle").text(recipeSubtitle($('.carousel div:first-child').attr('name')));
				$("#recipetitle").fadeIn('slow');
				data.items.old.find( 'img' ).stop().css({
					width: 410,
					height: 230,
					marginTop: 0,
					marginLeft: 0
				});
			}
		},
		onCreate: function( data ) {
			animate( data.items, pDur + ( dur *2 ) );
		}
	});
	
	function recipeSubtitle(foodNum) {
		str = "INCLUDES " + foodNum
		if(foodNum > 1) {
			return str + " FOODS FROM YOUR CART";
		} else if (foodNum == 1) {
			return str + " FOOD FROM YOUR CART";
		} else {
			return "";
		}
	}

	function animate( item, dur ) {
		var obj = {
			width: 534,
			height: 300
		};
		obj.marginTop = -70;
		switch( Math.ceil( Math.random() * 2 ) ) {
			case 1:
				obj.marginLeft = 0;
				break;
			case 2:
				obj.marginLeft = -124
				break;
		}
		item.find( 'img' ).animate(obj, dur, 'linear');
	}
 
};
genShow();

//play sound
$('input, button, .dropentry, .fooditem, a').click(function() {
	$("#tapsound")[0].load();
	$("#tapsound")[0].play();
});

// Update cart and recipes
$(function() {
	//save recipe
	$('.recipemiddle').on('click', function(e) {
		$.post($SCRIPT_ROOT + '/_save_recipe', {
			savedRecipe: $('.carousel div:first-child').attr('id')
		});
	});

	//Handle cart and recipe replacements
    $('.fooditem:not(.deliverablefood)').on('click', function(e) {
    	prevID = $(this).attr('id');
      	$.getJSON($SCRIPT_ROOT + '/_update_cart', {
      		itemToReplace: prevID
      	}, function(data) {
      		oldID = "#"+prevID;
      		$(oldID).fadeOut('fast').promise().done(function(){
      			//food item
      			$(oldID + ' .title div').text(data.name);
      			$(oldID + ' .image img').attr('src','static/img/foods/'+data.img);
      			$(oldID).fadeIn('fast');
      			$(oldID).attr('id',data.id);

      			//recipes
      			$('.carousel').empty();
      			data.recipes.forEach(function(recipe){
      				$('.carousel').append('<div title="'+recipe['name']+'" name="'+recipe['foodsused']+'" id="'+recipe['id']+'"><img src="static/img/recipes/'+recipe['img']+'" border="0" width=534 height=300/></div>');
      			});
      			$('#reciperight').click();
      		});
      });
      return false;
    });
  });

var wall1, wall2, wall3, wall4;
function masonLoad() {
  wall1 = new Masonry( document.getElementById('category1'), {});
  wall2 = new Masonry( document.getElementById('category2'), {});
  wall3 = new Masonry( document.getElementById('category3'), {});
  wall4 = new Masonry( document.getElementById('category4'), {});
};
window.onload = masonLoad();



//Toggle recipe view
$('.recipetogglebtn').click(function(){
	$(this).val($(this).val() == "SHOW ALL INGREDIENTS AND INSTRUCTIONS" ? "HIDE ALL INGREDIENTS AND INSTRUCTIONS" : "SHOW ALL INGREDIENTS AND INSTRUCTIONS");
	$(this).prev().toggle(0,function(){masonLoad()});
});
/*automatically resize title text*/
/*$(function() {
	$( ".title" ).each(function(){
		while($(this).find('div').height()+12 > $(this).height()) {
			$(this).css('font-size', (parseInt($(this).find('div').css('font-size')) - 1) + "px" );
		}
	});
});*/
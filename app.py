#!/usr/bin/env python
"""
INDEXING:
db.recipes.ensureIndex({"foodsused":"text","nutrition.Calories":1,"nutrition.Sodium":1,"nutrition.Percent Calories From Fat":1})
db.foods.ensureIndex({"id":"text","name":"text","combos":1,"nutrition.Sodium":1,"nutrition.Potassium":-1,"nutrition.Total Fat":1})

PRODUCTION DEPLOYMENT:
--Hide food codes, pass less info and use more ajax?
--Optimize JS, etc.
--Use sessions/isolate sessions so not all carts everywhere are the same
--use gunicorn (only w/ gevent) behind nginx ...disable buffering?
"""

from gevent import monkey; monkey.patch_all()
from gevent.pywsgi import WSGIServer
from flask import Flask, render_template, url_for, request, jsonify
from flask.ext.pymongo import PyMongo
from operator import itemgetter
from collections import defaultdict
import networkx as nx
import random


app = Flask('foodbase')
mongo = PyMongo(app)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = '85(1a^0^hj*&-a_0matxkekxhd2y5kpery5t08f!zdpzrq2Vrr'
app.config['SERVER_NAME'] = 'localhost:5000'

def removeNonAscii(s): return "".join(filter(lambda x: ord(x)<128, s))

class ShoppingCart:
	ignoreCodes = []

	def __init__(self, dietName):
		"""Initializes list of foods in cart based on passed diet name."""
		if dietName is 'dash':
			self.foods = [
				# Grain 1
				{'id':'57123000', 'groups':['57', '551', '552', '562']},
				# Grain 2
				{'id':'51201010', 'groups':['522', '512', '513', '516']},
				# Grain 3
				{'id':'56101000', 'groups':['56', '522', '512', '513', '516']},
				# Meat 1
				{'id':'25230905', 'groups':['26', '24']},
				# Meat 2
				{'id':'24122120', 'groups':['26', '24']},
				# Fruit 1
				{'id':'61119010', 'groups':['611', '631', '632', '62', '612']},
				# Fruit 2
				{'id':'63101000', 'groups':['611', '631', '632', '62', '612']},
				# Fruit 3
				{'id':'63203010', 'groups':['632', '611', '631', '62', '612']},
				# Fruit 4
				{'id':'62109100', 'groups':['62', '632', '611', '631', '612']},
				# Vegetable 1
				{'id':'75109000', 'groups':['7']},
				# Vegetable 2
				{'id':'73101010', 'groups':['7']},
				# Vegetable 3
				{'id':'74101000', 'groups':['7']},
				# Legumes 1
				{'id':'41102000', 'groups':['41', '7']},
				# Snacks 1
				{'id':'42101210', 'groups':['421', '431']},
				# Dairy 1
				{'id':'11112210', 'groups':['110', '111', '112', '113', '114', '131', '132', '14']},
				# Dairy 2
				{'id':'11411300', 'groups':['110', '111', '112', '113', '114', '131', '132', '14']}
			]
			self.prepareCart()
		else:
			raise Exception('Unknown diet specified') 

	def prepareCart(self):
		"""Updates food list with corresponding display name and combo code from database."""
		cartIDs = [food['id'] for food in self.foods]
		with app.app_context():
			dbFoods = mongo.db.foods.find({'id':{'$in':cartIDs}},{'id':1,'name':1,'combos':1})
		for dbFood in dbFoods:
			cartIndex = map(itemgetter('id'), self.foods).index(dbFood['id'])
			self.foods[cartIndex]['name'] = dbFood['name']
			self.foods[cartIndex]['combos'] = dbFood['combos']

	def retrieveCart(self):
		"""Returns a list of food items to be used in user interface"""
		return [{'id':food['id'],'name':food['name'].upper(),'img':food['id']+'.jpg'} for food in self.foods]

	def retrieveCartIDs(self):
		"""Returns a list of food code IDs corresponding to items in the cart."""
		return [food['id'] for food in self.foods]

	def dashFilter(self, rItem):
		"""Returns top foods with lowest sodium and higest potassium in indicated food groups"""
		#self.ignoreCodes.append(rItem)
		ignoreList = self.ignoreCodes + self.retrieveCartIDs()
		regexstr = "|".join("^"+item for item in next((food['groups'] for food in self.foods if food['id'] == rItem), None))
		with app.app_context():
			return mongo.db.foods.find({'id':{'$regex':regexstr, '$nin':ignoreList}},{"id":1,"name":1,"combos":1,"_id":0,"nutrition.Sodium":1,"nutrition.Potassium":1}).sort([("nutrition.Sodium", 1), ("nutrition.Total Fat", 1),("nutrition.Potassium", -1)])

	def comboFilter(self,topFoods, oldCart):
		"""Finds a new replacement cart food that best combines with the other items in the cart."""
		comparisonDict = {}

		topFoods=list(topFoods)

		for replacementFood in topFoods:
			foodGraph = nx.Graph()
			tempCart = oldCart + [replacementFood];
			for item in tempCart:
				foodGraph.add_node(item["id"])

			for cartItem in (t for t in tempCart if 'combos' in t):
				for comboNum, comboWeight in cartItem['combos'].items():
					if comboNum in foodGraph:
						foodGraph.add_edge(comboNum, cartItem["id"], weight=comboWeight)

			#find average shortest path length between topFood and all other reachable items
			#shrtPaths = nx.single_source_dijkstra_path_length(foodGraph,replacementFood["id"])
			#avgLength = sum(shrtPaths.values())/len(shrtPaths)
			
			#append avg path length to comparisonDict
			#comparisonDict[replacementFood['id']] = avgLength

			#append average clustering coefficient to comparisonDict
			comparisonDict[replacementFood['id']] = nx.average_clustering(foodGraph,weight='weight')

		#find food id with shorest path length
		#if sum(comparisonDict.values()) == 0:
		#	topReplacement = random.choice(list(comparisonDict.keys()))
		#else:
		#	comparisonDict = {key: value for key, value in comparisonDict.items() if int(value) is not 0}
		#	topReplacement = min(comparisonDict, key=comparisonDict.get)

		#find maximum clustering coefficient
		topReplacement = max(comparisonDict, key=comparisonDict.get)

		#return matching replacement dict
		return next(item for item in topFoods if item["id"] == topReplacement)

	def randomFilter(self,topFoods):
		"""Finds a random replacement cart food"""
		topFoods=list(topFoods)
		return random.choice(topFoods)

	def updateCart(self, replaceItem):
		"""Replaces specified item with cart according to algorithm and returns new item"""
		topFoods = self.dashFilter(replaceItem)
		restOfCart = [item for item in self.foods if item["id"] != replaceItem]
		#topCombo = self.comboFilter(topFoods, restOfCart)
		topCombo = self.randomFilter(topFoods)
		self.foods = [{"id":topCombo["id"],"name":topCombo['name'],"groups":item['groups'],"combos":topCombo['combos']} if item["id"] == replaceItem else item for item in self.foods]
		return {'id':topCombo['id'],'name':topCombo['name'].upper(),'img':topCombo['id']+'.jpg'}


class RecipeCollection:
	savedRecipes = []

	def __init__(self, foods):
		"""Initializes a list of recipes based on pass food code IDs."""
		self.prepareRecipes(foods)
		self.savedRecipes = []

	def prepareRecipes(self, foods):
		"""Retrieve recipes from database that correspond to specific nutritional requirements and contain cart items"""
		if type(foods) is list and all(len(food) == 8 for food in foods):
				with app.app_context():
					dbRecipes = mongo.db.recipes.aggregate([{"$match":{"categories": {"$nin": ['Cakes', 'Desserts', 'Breads/Rolls', 'Beverages']},"nutrition.Percent Calories From Fat": {"$lt": 25},"nutrition.Calories": {"$ne": 0},"nutrition.Sodium": {"$lte": 200}}},{"$unwind":"$foodsused"},{"$match":{"foodsused":{"$in":foods}}},{"$group":{"_id": {"id":"$id","name":"$name","categories":"$categories","titlefoods":"$titlefoods"}, "ingmatchcount": {"$sum": 1},"foodsused":{"$push":"$foodsused"}}},{"$sort":{"ingmatchcount":-1}},{"$limit":50}])
				
				# Sort by number of cart foods in titlefoods
				key = lambda recipe: len([code for code in foods if code in recipe['_id']['titlefoods']])
				dbRecipes['result'].sort(key=key, reverse=True)

				#only return recipes where at least one ingredient in cart is a 'main' ingredient -- returns too few foods sometimes
				#newRecipes = (recipe for recipe in dbRecipes['result'] if len([code for code in foods if code in recipe['_id']['titlefoods']]) > 0)

				#only return recipes where number of ingredients in cart that are 'main' title ingredient > 0 ONLY in cases where title array length > 0
				newRecipes = (recipe for recipe in dbRecipes['result'] if len([code for code in foods if code in recipe['_id']['titlefoods']]) > 0 or len(recipe['_id']['titlefoods'])==0)

				self.recipes = [{'id':recipe['_id']['id'],'name':recipe['_id']['name'],'categories':recipe['_id']['categories'],'foodsused':recipe['ingmatchcount']} for recipe in newRecipes]
		else:
			raise Exception('Unable to generate recipe collection due to malformed food list.')

	def getMasterCategory(self, categories):
		for category in categories:
			if category in ['Juice', 'Beverages', 'Bverages','Juices']:
				return 'BEVERAGES'
			elif category in ['Breakfast','Quiche', 'Fruit', 'Cereal','Waffles', 'Appetizer', 'Breakfast/Brunch', 'Brunch', 'Pancakes/Waffles','Omelets','Fritters', 'Eggs Dishes', 'Eggs', 'Pancakes', 'Egg Dishes','Muffins' ]:
				return 'BREAKFAST AND BRUNCH'
			elif category in ['Bread/Rolls','Spring Rolls', 'Candy', 'Accompniment','Brownies','Pastry', 'Preserves', 'Sorbets/Ices','Cheesecakes','Cheese', "Hors D'Oeuvre", 'Conserves', 'Tarts','Sweetbreads', 'Pickles/Relishes', 'Frostings/Fillings', 'Stock','Cake','Seasonings','Dessert','Condiments', 'Filling', 'Marmalades', 'Vinegars','Miscellaneous', 'Pies', 'Gravies','Indian', 'Frogs Legs', 'Jellies/Jams','Side Dishes', 'Side Dish','Custards','Dessrets', 'Dips/Spreads',"Hors d'Oeuvres", 'Butters/Spreads', 'Cakes', 'Custard', 'Breads/Rolls',  'Accompaniment',  "Hors D'deuvres",'Dressing/Stuffing','Comdiments','Fillings', 'Snacks','Deserts','Cheesecake','Pasties', 'Stuffings', 'Chutneys', 'Condiment', 'Ice Cream', 'Pastries', 'Cookies','Fillings/Frostings','Candies', 'Frostings', "Hors D'Oeuvres", 'Desserts', 'Ices/Sorbets','Salsa', 'Frosting/Icing',  'Syrups', 'Custards/Puddings', 'Compound Butters','Vegan', 'Eg Dishes', 'Fish Ocean', 'Fish (Fresh Water)', 'Smoking', 'Puddings', 'Jams/Jellies','Accompaniments', 'Biscuits','Stuffing', 'Dressings']:
				return 'SNACKS AND SIDE DISHES'
			else:
				return 'LUNCH AND DINNER'
				"""['Small Game','Casseroles', 'Upland Birds', 'Muskox', 'Clams/Mussels', 'Vehetables', 'Rabbit', 'Iranian','Veal', 'Exotic', 'Frog Legs','Noodles', 'Turkey', 'Poulyrt','Vegetables', 'Salted Cod', 'Squash', 'Emu / Ostrich', 'Game', '* Syrian', 'Greens', 'Quiches', 'Ostrich','First Course', 'La_times', 'Rabbit / Hare', 'Perch', 'Chinese', 'Shellfood','Meatloaf', 'Onions', 'Spinach', 'Main Dish', 'Brazilian', 'Kebabs', 'Empanadas', 'Butters', 'Corn', 'Peas', 'Roughfish', 'Oxtails', 'Liver', 'Partridge', 'Chutney', 'Refrigerator', 'Soups/Stews', 'Tortillas', 'Vegetarian', 'Smoker',  'German', 'Quesadillas', 'Soops/Stews',  'Dide Dish', 'Guinea Hens', 'Vietnamese', 'Microwave', 'Alligator / Crocodile','Pizze', 'Christmas', 'Pizza', 'Moose', 'Croquettes', 'Hanukkah','Grains', 'Dried Beans', '* Spanish','Variety Meats', 'Chowder', 'Souffles', 'Japanese','Copycat', 'Enchiladas', 'Sandwiches','Short Ribs', 'Bisque', 'Woodcock / Timberdoodle', 'Dim Sum', 'Kangaroo', 'Armenian','Appetzers', 'Dumplings','Valentines', 'Squid', 'Moroccan', 'Goose', 'Quail', 'Seafood)', 'Venison','Korean', 'Freezing', 'Costa Rican', 'String Beans', 'Tomatoes',  'Dairy Free', 'Cuban','Marinades', 'Mixes', 'Salads Shrimp', 'Beans', 'Paella', 'Frittata', 'Buffalo', 'Soup', 'Mushrooms', 'Lamb', 'Wraps', 'Cupcakes', 'East Indian', 'Swordfish','Stocks', 'Dove', 'Starter', 'Cold Appetizers', 'Egg/Spring Rolls', 'Ribs', 'Pork', 'Shrimp', 'Eggplant', 'Tongue', 'Seafood Soups', 'Tuna', 'Kwanzaa', 'Grilling', 'Duck','Information', 'Sausage', 'Spam', 'Crab', 'Vegetable', 'Rice', 'Jewish', 'Calamari/Squid','Poultry',  'Gorditas', 'Fajitas', 'Lynx', 'Fish (Ffresh Water)', 'Portuguese', 'Sopus/Stews', 'Stir-Fry', 'Panfish', 'Egg Free', 'Ham', 'Comments', 'Goat', 'Bass', 'Muslim', 'Spring/Summer Rolls', 'Sardines', 'Drying', 'Fish & Game', 'Albanian', 'Thanksgiving', 'Spareribs','Bear', 'Crayfish', 'Italian', 'Walleye', 'Lobster', 'Spice Blend', 'Main Dishes', 'Artichokes',  'Ham/Pork', 'Indonesian', 'Hawaiian', 'Striped Bass', 'Purim', 'Thai', 'Yurkey', 'Fish (Salt Water)','Waterfowl', 'African', 'Soup/Stews','Caribo', 'Greek', 'Fish (Freshwater)', 'Fish', 'Preserving','Beaver','Opossum', 'Scallops', 'Vegetable Soups', 'Holiday','Wild Duck', 'Roll Ups', 'Oysters', 'Carp', 'Salmon', 'Tacos', 'Passover', 'Bluegill / Crappie', 'Seafood', 'Crockpot', 'Main Dish Vegetables', 'Main Dish)','Wild Geese', 'Halloween', 'Low Fat', 'Easter', 'Kabobs', 'Trout', 'Squirrel', 'Amphibians', 'Low-Fat', 'Sausages', 'New Import', 'Pasta', 'Lebanese', 'Potatoes', 'Emu/Ostrich', 'Wild Turkey', 'Escargot/Snails', 'Marsh Birds','Ramadan', 'Meats', 'Sauces','Crawfish', 'Fondue', 'Spice Blends', 'Squid/Calamari',  'Holidays', 'Ethnic', 'Filipino', 'Restaurant','. Information','Pheasant','Mountain Sheep','Pot-Pies','Beef','Appetizers', 'Meatballs',  'Catfish', 'New Year', 'Meats Combo', 'Gifts', 'Rubs', 'Big Game', 'Fish (Ocean)', 'Tapas', 'Halibut', 'Fruits', 'Raccoon', 'Canning', 'Bison / Buffalo', 'Pot Pies', 'Fish(Ocean)', 'Marinade',  'Elk', 'Shellfish', "Calf's Liver", 'Shad','Seefood', 'Entree', 'Chicken Chinese', 'Cornish Hens', 'Spare Ribs', 'Rice/Graind', 'Rice/Grains', 'Burritos', 'Barbecue', 'Fish/Seafood', 'Wild Boar', 'Tamales','Squab','Snails/Escargot',  'Potstickers', 'Cassaroles', 'Mexican', 'Grouse', 'Spanish', 'Chicken', 'Salads', 'Salads/Dressings','Basic Salads','Frittatas','Springs/Summer Rolls','Sweet Potatoes','Guatemalan','Chili', 'Shelfish','Asparagus','Zucchini']"""


	def retrieveRecipes(self):
		"""Returns a list of recipes to be used in user interface"""
		return [{'id':recipe['id'], 'name':str(removeNonAscii(recipe['name'])).upper(), 'foodsused':recipe['foodsused'],'img':str(recipe['id'])+'.jpg'} for recipe in self.recipes]

	def retrieveSavedRecipes(self):
		"""Queries all saved recipes from the database and returns to deliverable"""
		#if len(self.savedRecipes) >= 10:
		suggestedRecipes = self.savedRecipes
		#else:
		#	suggestedRecipes = self.savedRecipes + [recipe for recipe in [r['id'] for r in self.recipes] if recipe not in self.savedRecipes]
		with app.app_context():
				dbSavedRecipes = mongo.db.recipes.find({"id":{"$in":suggestedRecipes}}); 
				preList = [recipe for recipe in dbSavedRecipes]
				masterList = {'BREAKFAST AND BRUNCH':[],'SNACKS AND SIDE DISHES':[],'LUNCH AND DINNER':[],'BEVERAGES':[]}
				for recipe in preList:
					masterList[self.getMasterCategory(recipe['categories'])].append(recipe)
				return masterList


	def saveRecipe(self,recipe):
		"""Add new recipe to saved list"""
		self.savedRecipes.append(int(recipe))
		self.savedRecipes = list(set(self.savedRecipes))

@app.route('/_update_cart')
def update_cart():
    replaceItem = request.args.get('itemToReplace', 0, type=str)
    newData = cart.updateCart(replaceItem)
    recipes.prepareRecipes(cart.retrieveCartIDs())
    newRecipes = recipes.retrieveRecipes();
    #random.shuffle(newRecipes)
    newData['recipes'] = newRecipes
    return jsonify(newData)

@app.route('/_save_recipe',methods = ['POST'])
def save_recipe():
	recipeToSave = request.form['savedRecipe']
	recipes.saveRecipe(recipeToSave)
	return recipeToSave

@app.route('/')
def index():
	return render_template('cart.html', cart=cart.retrieveCart(), recipes=recipes.retrieveRecipes())

@app.route('/results')
def deliver():
	return render_template('deliverable.html', cart=cart.retrieveCart(), recipes=recipes.retrieveSavedRecipes())

@app.route('/datatest')
def data():
	return render_template('data.html')

if __name__ == '__main__':
  cart = ShoppingCart('dash')
  recipes = RecipeCollection(cart.retrieveCartIDs())
  server = WSGIServer(('', 5000), app)
  server.serve_forever()
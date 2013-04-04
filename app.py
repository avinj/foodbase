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
import networkx as nx
import random


app = Flask('foodbase')
mongo = PyMongo(app)
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = '85(1a^0^hj*&-a_0matxkekxhd2y5kpery5t08f!zdpzrq2Vrr'
app.config['SERVER_NAME'] = 'localhost:5000'


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
		"""Returns top 10 foods with lowest sodium and higest potassium in indicated food groups"""
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

	def updateCart(self, replaceItem):
		"""Replaces specified item with cart according to algorithm and returns new item"""
		topFoods = self.dashFilter(replaceItem)
		restOfCart = [item for item in self.foods if item["id"] != replaceItem]
		topCombo = self.comboFilter(topFoods, restOfCart)
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
					dbRecipes = mongo.db.recipes.aggregate([{"$match":{"categories": {"$nin": ['Cakes', 'Desserts', 'Breads/Rolls', 'Beverages']},"nutrition.Percent Calories From Fat": {"$lt": 25},"nutrition.Calories": {"$ne": 0},"nutrition.Sodium": {"$lte": 200}}},{"$unwind":"$foodsused"},{"$match":{"foodsused":{"$in":foods}}},{"$group":{"_id": {"id":"$id","name":"$name"}, "count": {"$sum": 1},"foodsused":{"$push":"$foodsused"}}},{"$sort":{"count":-1}},{"$limit":10}])
				
				self.recipes = [{'id':recipe['_id']['id'],'name':recipe['_id']['name'],'foodsused':recipe['count']} for recipe in dbRecipes['result']]
		else:
			raise Exception('Unable to generate recipe collection due to malformed food list.')

	def retrieveRecipes(self):
		"""Returns a list of recipes to be used in user interface"""
		return [{'id':recipe['id'], 'name':str(recipe['name']).upper(), 'foodsused':recipe['foodsused'],'img':str(recipe['id'])+'.jpg'} for recipe in self.recipes]

	def retrieveSavedRecipes(self):
		"""Queries all saved recipes from the database and returns to deliverable"""
		#if len(self.savedRecipes) >= 10:
		suggestedRecipes = self.savedRecipes
		#else:
		#	suggestedRecipes = self.savedRecipes + [recipe for recipe in [r['id'] for r in self.recipes] if recipe not in self.savedRecipes]
		with app.app_context():
				dbSavedRecipes = mongo.db.recipes.find({"id":{"$in":suggestedRecipes}}); 
				return [recipe for recipe in dbSavedRecipes]

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
    random.shuffle(newRecipes)
    newData['recipes'] = newRecipes
    return jsonify(newData)

@app.route('/_save_recipe',methods = ['POST'])
def save_recipe():
	recipeToSave = request.form['savedRecipe']
	recipes.saveRecipe(recipeToSave)
	return recipeToSave

@app.route('/')
def index():
	global cart
	global recipes
	cart = ShoppingCart('dash')
  	recipes = RecipeCollection(cart.retrieveCartIDs())
	return render_template('cart.html', cart=cart.retrieveCart(), recipes=recipes.retrieveRecipes())

@app.route('/results')
def deliver():
	return render_template('deliverable.html', cart=cart.retrieveCart(), recipes=recipes.retrieveSavedRecipes())


if __name__ == '__main__':
  server = WSGIServer(('', 5000), app)
  server.serve_forever()
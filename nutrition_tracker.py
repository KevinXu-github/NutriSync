import requests
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
import time

class HybridNutritionTracker:
    def __init__(self):
        # USDA FoodData Central API (Primary source)
        self.usda_api_key = "YzTOpkjoupRbj0RJ7mzt5Jjp6igfFgg1uAz1u6rg"
        self.usda_base_url = "https://api.nal.usda.gov/fdc/v1"
        
        # Open Food Facts API (Secondary source)
        self.off_base_url = "https://world.openfoodfacts.net/api/v2"
        
        # Cache for nutrition lookups
        self.nutrition_cache = {}
        self.cache_file = "nutrition_cache.json"
        # Disabled cache for now to ensure fresh data
        # self.load_cache()

    def load_cache(self):
        """Load nutrition cache from file"""
        try:
            with open(self.cache_file, 'r') as f:
                self.nutrition_cache = json.load(f)
        except FileNotFoundError:
            self.nutrition_cache = {}
        except Exception as e:
            print(f"Error loading nutrition cache: {e}")
            self.nutrition_cache = {}

    def save_cache(self):
        """Save nutrition cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.nutrition_cache, f, indent=2)
        except Exception as e:
            print(f"Error saving nutrition cache: {e}")

    def lookup_by_fdc_id(self, fdc_id: int) -> Optional[dict]:
        """Direct lookup by FDC ID to verify nutrition data"""
        try:
            print(f"🔍 Direct FDC ID lookup: {fdc_id}")
            
            lookup_url = f"{self.usda_base_url}/food/{fdc_id}"
            params = {'api_key': self.usda_api_key}
            
            response = requests.get(lookup_url, params=params, timeout=15)
            
            if response.status_code == 200:
                food_data = response.json()
                
                print(f"📋 Direct lookup result:")
                print(f"   Description: {food_data.get('description', 'N/A')}")
                print(f"   Data Type: {food_data.get('dataType', 'N/A')}")
                
                # Show portion information
                food_portions = food_data.get('foodPortions', [])
                if food_portions:
                    print(f"   Available Portions:")
                    for i, portion in enumerate(food_portions):
                        portion_desc = portion.get('portionDescription', 'Unknown')
                        gram_weight = portion.get('gramWeight', 'Unknown')
                        print(f"     {i+1}. {portion_desc} = {gram_weight}g")
                
                # Extract nutrition for first/default portion
                nutrients = {}
                for nutrient in food_data.get('foodNutrients', []):
                    nutrient_id = nutrient.get('nutrientId')
                    value = nutrient.get('value', 0) or 0
                    
                    if nutrient_id == 1008:  # Calories
                        nutrients['calories'] = value
                    elif nutrient_id == 1003:  # Protein  
                        nutrients['protein'] = value
                    elif nutrient_id == 1093:  # Sodium
                        nutrients['sodium'] = value
                
                print(f"   Default nutrition: {nutrients.get('calories', 0)} cal, {nutrients.get('protein', 0)}g protein, {nutrients.get('sodium', 0)}mg sodium")
                
                return food_data
            else:
                print(f"❌ Direct lookup failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Direct lookup error: {e}")
            return None

    def normalize_food_name(self, name: str) -> str:
        """Normalize food name for better matching"""
        # Handle unicode
        name = name.encode('ascii', 'ignore').decode('ascii')
        
        # Convert to lowercase
        name = name.lower()
        
        # Remove common words and symbols
        name = re.sub(r'[®™©]', '', name)
        name = re.sub(r'\s*\([^)]+\)\s*', '', name)  # Remove parentheticals
        name = re.sub(r'\s*\[[^\]]+\]\s*', '', name)  # Remove brackets
        
        # Clean up whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name

    def create_cache_key(self, restaurant: str, item_name: str) -> str:
        """Create cache key for nutrition data"""
        return f"{restaurant.lower()}_{self.normalize_food_name(item_name)}"

    def search_usda_api(self, food_name: str, restaurant: str = "") -> Optional[dict]:
        """Search USDA FoodData Central API (Primary source)"""
        try:
            clean_name = self.normalize_food_name(food_name)
            
            # Enhanced search queries for USDA (using exact terms that work on USDA website)
            search_queries = [
                f"{restaurant}s {clean_name}",  # "McDonalds mcdouble" (note the 's')
                f"{restaurant} {clean_name}",   # "McDonald mcdouble"  
                clean_name,  # Just the item
                f"{clean_name} {restaurant}",   # "mcdouble McDonald"
            ]
            
            for query in search_queries:
                if not query.strip():
                    continue
                    
                print(f"🔍 USDA API search: '{query.strip()}'")
                
                search_url = f"{self.usda_base_url}/foods/search"
                params = {
                    'api_key': self.usda_api_key,
                    'query': query.strip(),
                    'pageSize': 25,
                    'dataType': ['Survey (FNDDS)', 'Branded', 'SR Legacy', 'Foundation'],  # Added Survey Foods!
                    'format': 'full'  # Request full data including portions
                }
                
                response = requests.get(search_url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('foods') and len(data['foods']) > 0:
                        print(f"📋 Found {len(data['foods'])} USDA results")
                        
                        # Enhanced scoring for USDA results
                        best_food = None
                        best_score = 0
                        
                        for i, food in enumerate(data['foods'][:10]):
                            food_description = food.get('description', '').lower()
                            brand_name = food.get('brandName', '').lower()
                            
                            print(f"   {i+1}. {food_description} ({brand_name})")
                            
                            score = 0
                            
                            # Restaurant/brand priority
                            if restaurant.lower() in food_description or restaurant.lower() in brand_name:
                                score += 10
                                print(f"      +10 Brand match")
                            
                            # Diet/zero calorie special handling
                            if 'diet' in clean_name or 'zero' in clean_name:
                                if 'diet' in food_description or 'zero' in food_description:
                                    score += 15  # High priority for diet matches
                                    print(f"      +15 Diet/zero match")
                                # Penalty for high-calorie results when searching for diet items
                                nutrients = food.get('foodNutrients', [])
                                calories = 0
                                for nutrient in nutrients:
                                    if nutrient.get('nutrientId') == 1008:  # Energy
                                        calories = nutrient.get('value', 0) or 0
                                        break
                                if calories > 50:  # Too high for diet drink
                                    score -= 10
                                    print(f"      -10 High calorie penalty for diet item")
                            
                            # Exact name matching
                            if clean_name in food_description:
                                score += 8
                                print(f"      +8 Exact name match")
                            
                            # Word matching
                            for word in clean_name.split():
                                if word in food_description:
                                    score += 2
                                    print(f"      +2 Word match: {word}")
                            
                            print(f"      Total score: {score}")
                            
                            if score > best_score:
                                best_score = score
                                best_food = food
                        
                        if best_food and best_score > 0:
                            print(f"✅ USDA best match (score {best_score}): {best_food.get('description', 'Unknown')}")
                            print(f"🔍 DEBUG INFO:")
                            print(f"   FDC ID: {best_food.get('fdcId', 'N/A')}")
                            print(f"   Data Type: {best_food.get('dataType', 'N/A')}")
                            print(f"   Brand Name: {best_food.get('brandName', 'N/A')}")
                            print(f"   Food Category: {best_food.get('foodCategory', 'N/A')}")
                            
                            # Check for portion information and scale if needed
                            food_portions = best_food.get('foodPortions', [])
                            scaling_factor = 1.0  # Default no scaling
                            
                            print(f"   🔍 Checking data type: '{best_food.get('dataType', 'N/A')}'")
                            print(f"   🔍 Food portions available: {len(food_portions)}")
                            print(f"   🔍 Raw foodPortions data: {food_portions}")
                            
                            if best_food.get('dataType') == 'Survey (FNDDS)':
                                print(f"   📏 Survey Foods (FNDDS) detected - checking portion sizes:")
                                
                                if food_portions:
                                    print(f"   Available Portions: {len(food_portions)}")
                                    
                                    # Look for the main serving portion (not 100g)
                                    target_portion = None
                                    for i, portion in enumerate(food_portions):
                                        portion_desc = portion.get('portionDescription', 'Unknown')
                                        gram_weight = portion.get('gramWeight', 100)
                                        print(f"     {i+1}. {portion_desc} = {gram_weight}g")
                                        
                                        # Look for the actual serving (not 100g reference)
                                        if gram_weight != 100 and ('cheeseburger' in portion_desc.lower() or 'sandwich' in portion_desc.lower() or 'piece' in portion_desc.lower() or 'double' in portion_desc.lower()):
                                            target_portion = portion
                                            scaling_factor = gram_weight / 100.0
                                            print(f"   ✅ Using portion: {portion_desc} ({gram_weight}g)")
                                            print(f"   🔢 Scaling factor: {gram_weight}g ÷ 100g = {scaling_factor:.2f}")
                                            break
                                    
                                    if scaling_factor == 1.0:
                                        print(f"   ⚠️ No specific serving found in available portions")
                                        print(f"   💡 Need to use direct FDC ID lookup to get portion data")
                                        
                                        # Try direct lookup for portion data
                                        fdc_id = best_food.get('fdcId')
                                        if fdc_id:
                                            print(f"   🔍 Attempting direct lookup for FDC ID: {fdc_id}")
                                            direct_food_data = self.lookup_by_fdc_id(fdc_id)
                                            if direct_food_data and direct_food_data.get('foodPortions'):
                                                direct_portions = direct_food_data.get('foodPortions', [])
                                                print(f"   📋 Direct lookup found {len(direct_portions)} portions:")
                                                
                                                for i, portion in enumerate(direct_portions):
                                                    portion_desc = portion.get('portionDescription', 'Unknown')
                                                    gram_weight = portion.get('gramWeight', 100)
                                                    print(f"     {i+1}. {portion_desc} = {gram_weight}g")
                                                    
                                                    if gram_weight != 100 and ('cheeseburger' in portion_desc.lower() or 'sandwich' in portion_desc.lower() or 'piece' in portion_desc.lower() or 'double' in portion_desc.lower()):
                                                        scaling_factor = gram_weight / 100.0
                                                        print(f"   ✅ Found correct portion via direct lookup: {portion_desc} ({gram_weight}g)")
                                                        print(f"   🔢 Scaling factor: {gram_weight}g ÷ 100g = {scaling_factor:.2f}")
                                                        break
                                else:
                                    print(f"   ⚠️ No portion data in search API response")
                                    print(f"   🔍 Trying direct FDC ID lookup for portion data...")
                                    
                                    # Try direct lookup for portion data
                                    fdc_id = best_food.get('fdcId')
                                    if fdc_id:
                                        direct_food_data = self.lookup_by_fdc_id(fdc_id)
                                        if direct_food_data and direct_food_data.get('foodPortions'):
                                            direct_portions = direct_food_data.get('foodPortions', [])
                                            print(f"   📋 Direct lookup found {len(direct_portions)} portions:")
                                            
                                            for i, portion in enumerate(direct_portions):
                                                portion_desc = portion.get('portionDescription', 'Unknown')
                                                gram_weight = portion.get('gramWeight', 100)
                                                print(f"     {i+1}. {portion_desc} = {gram_weight}g")
                                                
                                                if gram_weight != 100 and ('cheeseburger' in portion_desc.lower() or 'sandwich' in portion_desc.lower() or 'piece' in portion_desc.lower() or 'double' in portion_desc.lower()):
                                                    scaling_factor = gram_weight / 100.0
                                                    print(f"   ✅ Found correct portion: {portion_desc} ({gram_weight}g)")
                                                    print(f"   🔢 Scaling factor: {gram_weight}g ÷ 100g = {scaling_factor:.2f}")
                                                    break
                            else:
                                print(f"   📏 Non-survey data, using values as-is")
                            
                            # Extract nutrition data from USDA with proper unit handling
                            nutrition = {
                                'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
                                'fiber': 0, 'sugar': 0, 'sodium': 0
                            }
                            
                            print(f"📊 Extracting USDA nutrients with unit validation:")
                            print(f"   Total nutrients found: {len(best_food.get('foodNutrients', []))}")
                            
                            for nutrient in best_food.get('foodNutrients', []):
                                nutrient_id = nutrient.get('nutrientId')
                                nutrient_name = nutrient.get('nutrientName', '')
                                value = nutrient.get('value', 0) or 0
                                unit_name = nutrient.get('unitName', '')
                                
                                # Apply scaling factor to the raw value
                                scaled_value = value * scaling_factor
                                
                                # Map USDA nutrient IDs with unit validation
                                if nutrient_id == 1008:  # Energy
                                    if unit_name.lower() in ['kcal', 'calories']:
                                        nutrition['calories'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Calories: {value} → {scaled_value:.0f} kcal (scaled)")
                                        else:
                                            print(f"   ✅ Calories: {scaled_value} kcal")
                                    elif unit_name.lower() in ['kj', 'kilojoules']:
                                        nutrition['calories'] = scaled_value / 4.184
                                        print(f"   🔄 Calories: {value} kJ → {nutrition['calories']:.1f} kcal (scaled)")
                                    
                                elif nutrient_id == 1003:  # Protein
                                    if unit_name.lower() in ['g', 'grams']:
                                        nutrition['protein'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Protein: {value}g → {scaled_value:.1f}g (scaled)")
                                        else:
                                            print(f"   ✅ Protein: {scaled_value}g")
                                    
                                elif nutrient_id == 1005:  # Carbohydrates
                                    if unit_name.lower() in ['g', 'grams']:
                                        nutrition['carbs'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Carbs: {value}g → {scaled_value:.1f}g (scaled)")
                                        else:
                                            print(f"   ✅ Carbs: {scaled_value}g")
                                    
                                elif nutrient_id == 1004:  # Total fat
                                    if unit_name.lower() in ['g', 'grams']:
                                        nutrition['fat'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Fat: {value}g → {scaled_value:.1f}g (scaled)")
                                        else:
                                            print(f"   ✅ Fat: {scaled_value}g")
                                    
                                elif nutrient_id == 1079:  # Fiber
                                    if unit_name.lower() in ['g', 'grams']:
                                        nutrition['fiber'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Fiber: {value}g → {scaled_value:.1f}g (scaled)")
                                        else:
                                            print(f"   ✅ Fiber: {scaled_value}g")
                                    
                                elif nutrient_id == 2000:  # Total sugars
                                    if unit_name.lower() in ['g', 'grams']:
                                        nutrition['sugar'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Sugar: {value}g → {scaled_value:.1f}g (scaled)")
                                        else:
                                            print(f"   ✅ Sugar: {scaled_value}g")
                                    
                                elif nutrient_id == 1093:  # Sodium
                                    if unit_name.lower() in ['mg', 'milligrams']:
                                        nutrition['sodium'] = scaled_value
                                        if scaling_factor != 1.0:
                                            print(f"   🔢 Sodium: {value}mg → {scaled_value:.0f}mg (scaled)")
                                        else:
                                            print(f"   ✅ Sodium: {scaled_value}mg")
                                    elif unit_name.lower() in ['g', 'grams']:
                                        nutrition['sodium'] = scaled_value * 1000
                                        print(f"   🔄 Sodium: {value}g → {nutrition['sodium']:.0f}mg (scaled)")
                            
                            nutrition.update({
                                'confidence': min(0.95, 0.7 + (best_score * 0.03)),
                                'source': 'usda_primary',
                                'matched_description': best_food.get('description', ''),
                                'brand': best_food.get('brandName', ''),
                                'data_type': best_food.get('dataType', '')
                            })
                            
                            print(f"✅ USDA nutrition: {nutrition['calories']} cal, {nutrition['protein']}g protein")
                            return nutrition
                        
                    print(f"❌ No good USDA matches for: '{query.strip()}'")
                else:
                    print(f"❌ USDA API error: {response.status_code}")
                
                time.sleep(0.1)  # Rate limiting
                
        except Exception as e:
            print(f"❌ USDA API exception: {e}")
            import traceback
            traceback.print_exc()
        
        return None

    def search_open_food_facts(self, food_name: str, restaurant: str = "") -> Optional[dict]:
        """Search Open Food Facts API (Secondary source)"""
        try:
            clean_name = self.normalize_food_name(food_name)
            
            search_queries = [
                f"{restaurant} {clean_name}",
                f"{clean_name} {restaurant}",
                clean_name,
            ]
            
            for query in search_queries:
                if not query.strip():
                    continue
                
                print(f"🔍 Open Food Facts search: '{query.strip()}'")
                
                search_url = f"{self.off_base_url}/search"
                params = {
                    'search_terms': query.strip(),
                    'search_simple': 1,
                    'action': 'process',
                    'page_size': 20,
                    'fields': 'product_name,brands,nutriments,nutrition_grades,categories_tags_en,code'
                }
                
                response = requests.get(search_url, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('products') and len(data['products']) > 0:
                        print(f"📋 Found {len(data['products'])} Open Food Facts results")
                        
                        best_product = None
                        best_score = 0
                        
                        for i, product in enumerate(data['products'][:10]):
                            product_name = product.get('product_name', '').lower()
                            brands = product.get('brands', '').lower()
                            
                            print(f"   {i+1}. {product_name} ({brands})")
                            
                            score = 0
                            
                            # Brand matching
                            if restaurant.lower() in brands or restaurant.lower() in product_name:
                                score += 8
                                print(f"      +8 Brand match")
                            
                            # Diet/zero handling
                            if 'diet' in clean_name or 'zero' in clean_name:
                                if 'diet' in product_name or 'zero' in product_name or 'light' in product_name:
                                    score += 12
                                    print(f"      +12 Diet/zero match")
                                
                                # Verify with actual calories
                                nutriments = product.get('nutriments', {})
                                calories_100g = nutriments.get('energy-kcal_100g', 0) or 0
                                if calories_100g < 5:
                                    score += 5
                                    print(f"      +5 Low calorie verified")
                            
                            # Name matching
                            if clean_name in product_name:
                                score += 6
                                print(f"      +6 Exact name match")
                            
                            # Word matching
                            for word in clean_name.split():
                                if word in product_name:
                                    score += 1
                                    print(f"      +1 Word match: {word}")
                            
                            print(f"      Total score: {score}")
                            
                            if score > best_score:
                                best_score = score
                                best_product = product
                        
                        if best_product and best_score > 0:
                            print(f"✅ Open Food Facts best match (score {best_score}): {best_product.get('product_name', 'Unknown')}")
                            
                            # Extract nutrition from Open Food Facts with proper unit handling
                            nutriments = best_product.get('nutriments', {})
                            
                            print(f"📊 Extracting Open Food Facts nutrients (per 100g) with unit validation:")
                            
                            # Open Food Facts stores data per 100g with specific unit conventions
                            nutrition = {
                                'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
                                'fiber': 0, 'sugar': 0, 'sodium': 0
                            }
                            
                            # Energy - try multiple formats
                            energy_kcal = (nutriments.get('energy-kcal_100g') or 
                                         nutriments.get('energy_100g') or 0)
                            if energy_kcal == 0:
                                # Try kJ and convert to kcal
                                energy_kj = nutriments.get('energy-kj_100g', 0) or 0
                                if energy_kj > 0:
                                    energy_kcal = energy_kj / 4.184
                                    print(f"   🔄 Energy: {energy_kj}kJ → {energy_kcal:.1f}kcal per 100g")
                            
                            nutrition['calories'] = energy_kcal
                            if energy_kcal > 0:
                                print(f"   ✅ Calories: {energy_kcal}kcal per 100g")
                            
                            # Macronutrients (all in grams per 100g)
                            nutrition['protein'] = nutriments.get('proteins_100g', 0) or 0
                            nutrition['carbs'] = nutriments.get('carbohydrates_100g', 0) or 0  
                            nutrition['fat'] = nutriments.get('fat_100g', 0) or 0
                            nutrition['fiber'] = nutriments.get('fiber_100g', 0) or 0
                            nutrition['sugar'] = nutriments.get('sugars_100g', 0) or 0
                            
                            print(f"   ✅ Protein: {nutrition['protein']}g per 100g")
                            print(f"   ✅ Carbs: {nutrition['carbs']}g per 100g") 
                            print(f"   ✅ Fat: {nutrition['fat']}g per 100g")
                            print(f"   ✅ Fiber: {nutrition['fiber']}g per 100g")
                            print(f"   ✅ Sugar: {nutrition['sugar']}g per 100g")
                            
                            # Sodium - handle unit conversion carefully
                            sodium_g = nutriments.get('sodium_100g', 0) or 0
                            sodium_mg = nutriments.get('salt_100g', 0) or 0  # Sometimes stored as salt
                            
                            if sodium_g > 0:
                                # Convert grams to milligrams
                                nutrition['sodium'] = sodium_g * 1000
                                print(f"   🔄 Sodium: {sodium_g}g → {nutrition['sodium']}mg per 100g")
                            elif sodium_mg > 0:
                                # If it's stored as salt, convert salt to sodium (salt = sodium * 2.54)
                                sodium_from_salt = sodium_mg / 2.54 * 1000  # Convert to mg
                                nutrition['sodium'] = sodium_from_salt
                                print(f"   🔄 Salt: {sodium_mg}g → Sodium: {sodium_from_salt:.1f}mg per 100g")
                            else:
                                nutrition['sodium'] = 0
                                print(f"   ⚠️ Sodium: 0mg per 100g (no data)")
                            
                            # Validate reasonable ranges for per 100g values
                            if nutrition['calories'] > 900:  # Very high for 100g
                                print(f"   ⚠️ Warning: High calories per 100g ({nutrition['calories']})")
                            if nutrition['protein'] > 100:  # Impossible
                                print(f"   ⚠️ Warning: Protein > 100g per 100g, likely unit error")
                                nutrition['protein'] = min(nutrition['protein'], 100)
                            
                            nutrition.update({
                                'confidence': min(0.85, 0.5 + (best_score * 0.04)),
                                'source': 'open_food_facts_secondary',
                                'matched_description': best_product.get('product_name', ''),
                                'brand': best_product.get('brands', ''),
                                'nutrition_grade': best_product.get('nutrition_grades', ''),
                                'per_100g': True  # Flag that this needs serving size conversion
                            })
                            
                            print(f"✅ Open Food Facts nutrition (per 100g): {nutrition['calories']} cal, {nutrition['protein']}g protein")
                            return nutrition
                        
                    print(f"❌ No good Open Food Facts matches for: '{query.strip()}'")
                else:
                    print(f"❌ Open Food Facts API error: {response.status_code}")
                
                time.sleep(0.2)  # Rate limiting
                
        except Exception as e:
            print(f"❌ Open Food Facts API exception: {e}")
            import traceback
            traceback.print_exc()
        
        return None

    def estimate_serving_size(self, food_name: str, restaurant: str = "") -> float:
        """Estimate serving size in grams for common restaurant items"""
        clean_name = self.normalize_food_name(food_name).lower()
        
        # Common serving sizes in grams (based on USDA standard reference)
        serving_sizes = {
            # Beverages (12 fl oz standard)
            'diet coke': 355, 'coke': 355, 'coca cola': 355,
            'pepsi': 355, 'sprite': 355, 'dr pepper': 355,
            'drink': 355, 'beverage': 355, 'soda': 355,
            
            # McDonald's specific (from USDA data)
            'french fries': 115,  # Medium fries
            'big mac': 230, 'quarter pounder': 200, 'mcdouble': 165,
            'chicken sandwich': 200, 'spicy crispy chicken sandwich': 200,
            'mcchicken': 143, 'chicken mcnuggets': 16,  # Per nugget
            'apple pie': 77, 'hash brown': 56,
            
            # Generic items
            'burger': 150, 'sandwich': 150, 'fries': 115,
            'nuggets': 16, 'pie': 77,
        }
        
        # Look for specific matches first
        for key, size in serving_sizes.items():
            if key in clean_name:
                print(f"📏 Estimated serving size: {size}g for {food_name}")
                return size
        
        # Category-based estimates
        if any(word in clean_name for word in ['drink', 'beverage', 'coke', 'pepsi', 'sprite']):
            return 355  # Standard 12 fl oz
        elif 'fries' in clean_name:
            return 115  # Medium fries
        elif any(word in clean_name for word in ['burger', 'sandwich']):
            return 150  # Average sandwich
        
        # Default
        print(f"📏 Using default serving size: 100g for {food_name}")
        return 100

    def get_nutrition_for_item(self, restaurant: str, item_name: str, quantity: int = 1) -> Optional[dict]:
        """Get nutrition information using hybrid approach with proper unit handling"""
        
        print(f"\n🔍 HYBRID LOOKUP: {item_name} from {restaurant}")
        print(f"🎯 Strategy: USDA (primary) → Open Food Facts (secondary)")
        print(f"📏 Quantity: {quantity}")
        
        # Step 1: Try USDA FoodData Central (Primary source)
        nutrition = self.search_usda_api(item_name, restaurant)
        
        if nutrition:
            print(f"✅ SUCCESS: Found via USDA (primary source)")
            print(f"📊 Original USDA data: {nutrition['calories']} cal, {nutrition['protein']}g protein")
            
            # USDA data is typically per serving, validate units and scale by quantity
            if quantity > 1:
                print(f"🔢 Scaling by quantity: {quantity}")
                for key in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar', 'sodium']:
                    if key in nutrition:
                        original_value = nutrition[key]
                        nutrition[key] = nutrition[key] * quantity
                        print(f"   {key}: {original_value} → {nutrition[key]}")
            
            # Add unit information for transparency
            nutrition['units'] = {
                'calories': 'kcal',
                'protein': 'grams', 
                'carbs': 'grams',
                'fat': 'grams',
                'fiber': 'grams',
                'sugar': 'grams',
                'sodium': 'milligrams'
            }
            
            return nutrition
        
        # Step 2: Try Open Food Facts (Secondary source)
        print(f"⚠️ USDA lookup failed, trying Open Food Facts...")
        nutrition = self.search_open_food_facts(item_name, restaurant)
        
        if nutrition:
            print(f"✅ SUCCESS: Found via Open Food Facts (secondary source)")
            print(f"📊 Original Open Food Facts data (per 100g): {nutrition['calories']} cal, {nutrition['protein']}g protein")
            
            # Open Food Facts data is per 100g, convert to serving size
            if nutrition.get('per_100g'):
                serving_size_g = self.estimate_serving_size(item_name, restaurant)
                conversion_factor = serving_size_g / 100.0
                
                print(f"🔄 Converting from per 100g to {serving_size_g}g serving (factor: {conversion_factor:.2f})")
                
                for key in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar', 'sodium']:
                    if key in nutrition:
                        original_value = nutrition[key]
                        nutrition[key] = nutrition[key] * conversion_factor
                        print(f"   {key}: {original_value}/100g → {nutrition[key]:.1f}/serving")
                
                del nutrition['per_100g']
            
            # Scale by quantity
            if quantity > 1:
                print(f"🔢 Scaling by quantity: {quantity}")
                for key in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar', 'sodium']:
                    if key in nutrition:
                        original_value = nutrition[key]
                        nutrition[key] = nutrition[key] * quantity
                        print(f"   {key}: {original_value:.1f} → {nutrition[key]:.1f}")
            
            # Add unit information for transparency
            nutrition['units'] = {
                'calories': 'kcal',
                'protein': 'grams',
                'carbs': 'grams', 
                'fat': 'grams',
                'fiber': 'grams',
                'sugar': 'grams',
                'sodium': 'milligrams'
            }
            
            # Validate final values are reasonable
            self.validate_nutrition_values(nutrition, item_name, quantity)
            
            return nutrition
        
        # Step 3: Both sources failed
        print(f"❌ FAILED: No nutrition data found in either USDA or Open Food Facts")
        return None

    def validate_nutrition_values(self, nutrition: dict, item_name: str, quantity: int):
        """Validate nutrition values are reasonable and units are correct"""
        print(f"🔍 Validating nutrition values for {quantity}x {item_name}:")
        
        # Reasonable ranges per serving
        calories = nutrition.get('calories', 0)
        protein = nutrition.get('protein', 0)
        carbs = nutrition.get('carbs', 0)
        fat = nutrition.get('fat', 0)
        sodium = nutrition.get('sodium', 0)
        
        warnings = []
        
        # Calorie validation
        if calories > 2000 * quantity:
            warnings.append(f"Very high calories: {calories} (>{2000 * quantity} expected)")
        elif calories < 0:
            warnings.append(f"Negative calories: {calories}")
            
        # Protein validation (shouldn't exceed total weight)
        if protein > 100 * quantity:  # More than 100g protein per serving is unusual
            warnings.append(f"Very high protein: {protein}g")
            
        # Sodium validation
        if sodium > 5000 * quantity:  # More than 5000mg per serving is very high
            warnings.append(f"Very high sodium: {sodium}mg")
        elif sodium < 0:
            warnings.append(f"Negative sodium: {sodium}mg")
            
        # Diet drink validation
        if 'diet' in item_name.lower() and calories > 10 * quantity:
            warnings.append(f"Diet item with high calories: {calories} (should be <10)")
            
        if warnings:
            print(f"   ⚠️ Validation warnings:")
            for warning in warnings:
                print(f"      - {warning}")
        else:
            print(f"   ✅ All values within reasonable ranges")
            
        print(f"   📊 Final values: {calories:.0f} cal, {protein:.1f}g protein, {sodium:.0f}mg sodium")

def enhance_order_with_nutrition(order_data: dict) -> dict:
    """
    Main function to enhance order data with nutrition information using hybrid approach
    """
    print(f"\n🍎 STARTING HYBRID NUTRITION ANALYSIS...")
    print(f"🏛️ Primary: USDA FoodData Central (US government database)")
    print(f"🌍 Secondary: Open Food Facts (international crowdsourced database)")
    print(f"💡 Strategy: Use USDA first, fallback to Open Food Facts")
    
    tracker = HybridNutritionTracker()
    enhanced_order = order_data.copy()
    
    restaurant = order_data.get('restaurant', 'Unknown')
    items = order_data.get('items', [])
    
    print(f"🏪 Restaurant: {restaurant}")
    print(f"📦 Items to analyze: {len(items)}")
    
    # Track totals and sources
    meal_totals = {
        'total_calories': 0,
        'total_protein': 0,
        'total_carbs': 0,
        'total_fat': 0,
        'total_fiber': 0,
        'total_sugar': 0,
        'total_sodium': 0
    }
    
    source_stats = {'usda_primary': 0, 'open_food_facts_secondary': 0, 'failed': 0}
    
    # Process each item
    enhanced_items = []
    for i, item in enumerate(items, 1):
        item_name = item.get('name', '')
        quantity = item.get('quantity', 1)
        price = item.get('price', 0)
        
        print(f"\n📋 Item {i}/{len(items)}: {quantity}x {item_name}")
        
        # Get nutrition data using hybrid approach
        nutrition = tracker.get_nutrition_for_item(restaurant, item_name, quantity)
        
        # Create enhanced item
        enhanced_item = {
            'quantity': quantity,
            'name': item_name,
            'price': price
        }
        
        if nutrition:
            enhanced_item['nutrition'] = nutrition
            
            # Add to meal totals
            meal_totals['total_calories'] += nutrition.get('calories', 0)
            meal_totals['total_protein'] += nutrition.get('protein', 0)
            meal_totals['total_carbs'] += nutrition.get('carbs', 0)
            meal_totals['total_fat'] += nutrition.get('fat', 0)
            meal_totals['total_fiber'] += nutrition.get('fiber', 0)
            meal_totals['total_sugar'] += nutrition.get('sugar', 0)
            meal_totals['total_sodium'] += nutrition.get('sodium', 0)
            
            # Track source statistics
            source = nutrition.get('source', 'unknown')
            if 'usda' in source:
                source_stats['usda_primary'] += 1
            elif 'open_food_facts' in source:
                source_stats['open_food_facts_secondary'] += 1
            
            print(f"   ✅ {nutrition.get('calories', 0):.0f} cal, {nutrition.get('protein', 0):.1f}g protein")
            print(f"   📊 Source: {nutrition.get('source', 'unknown')} (confidence: {nutrition.get('confidence', 0):.2f})")
        else:
            enhanced_item['nutrition'] = None
            source_stats['failed'] += 1
            print(f"   ❌ No nutrition data found")
        
        enhanced_items.append(enhanced_item)
    
    # Calculate macro percentages
    total_calories = meal_totals['total_calories']
    if total_calories > 0:
        meal_totals['macro_percentages'] = {
            'protein': round((meal_totals['total_protein'] * 4 / total_calories) * 100, 1),
            'carbs': round((meal_totals['total_carbs'] * 4 / total_calories) * 100, 1),
            'fat': round((meal_totals['total_fat'] * 9 / total_calories) * 100, 1)
        }
    else:
        meal_totals['macro_percentages'] = {'protein': 0, 'carbs': 0, 'fat': 0}
    
    # Update the order data
    enhanced_order['items'] = enhanced_items
    enhanced_order['meal_totals'] = meal_totals
    enhanced_order['nutrition_timestamp'] = datetime.now().isoformat()
    enhanced_order['source_statistics'] = source_stats
    
    # Print comprehensive summary
    print(f"\n📊 HYBRID NUTRITION ANALYSIS COMPLETE")
    print(f"🏪 Restaurant: {restaurant}")
    print(f"💰 Total Cost: ${order_data.get('total', 0):.2f}")
    print(f"🔥 Total Calories: {meal_totals['total_calories']:.0f}")
    print(f"🥩 Protein: {meal_totals['total_protein']:.1f}g ({meal_totals['macro_percentages']['protein']:.1f}%)")
    print(f"🍞 Carbs: {meal_totals['total_carbs']:.1f}g ({meal_totals['macro_percentages']['carbs']:.1f}%)")
    print(f"🧈 Fat: {meal_totals['total_fat']:.1f}g ({meal_totals['macro_percentages']['fat']:.1f}%)")
    print(f"🧂 Sodium: {meal_totals['total_sodium']:.0f}mg")
    print(f"\n📈 DATA SOURCES:")
    print(f"   🏛️ USDA Primary: {source_stats['usda_primary']}/{len(items)} items")
    print(f"   🌍 Open Food Facts Secondary: {source_stats['open_food_facts_secondary']}/{len(items)} items")
    print(f"   ❌ Failed: {source_stats['failed']}/{len(items)} items")
    
    success_rate = ((source_stats['usda_primary'] + source_stats['open_food_facts_secondary']) / len(items)) * 100
    print(f"   ✅ Overall Success Rate: {success_rate:.1f}%")
    
    return enhanced_order
import requests
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
import time

class NutritionixTracker:
    """
    A class to track nutritional information for food items using the Nutritionix API.
    It includes methods for searching items, fetching nutrition data, and caching results.
    """
    def __init__(self):
        """
        Initializes the tracker with API credentials, endpoints, and loads the cache.
        """
        # --- Configuration ---
        # NOTE: It's best practice to load credentials from environment variables
        # or a config file rather than hardcoding them.
        self.app_id = "c61083f5"
        self.app_key = "56f69812cb54dca287ccca8f0c3355b2"
        
        # Nutritionix API endpoints
        self.instant_endpoint = "https://trackapi.nutritionix.com/v2/search/instant"
        self.nutrients_endpoint = "https://trackapi.nutritionix.com/v2/natural/nutrients"
        
        # Request timeout in seconds
        self.timeout = 10

        # --- Cache Setup ---
        self.cache_file = "nutritionix_cache.json"
        self.cache = self.load_cache()
    
    def load_cache(self) -> Dict:
        """
        Loads the nutrition cache from a local JSON file.
        Returns an empty dictionary if the file doesn't exist or is invalid.
        """
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return an empty cache if file is not found or corrupted
            return {}

    def save_cache(self):
        """
        Saves the current state of the cache to a local JSON file.
        """
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=4)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def clean_item_name(self, item_name: str) -> str:
        """
        Cleans up an item name by removing common clutter from delivery service emails.
        
        Examples:
        - "Spicy Chicken Sandwich (Individual Items)" -> "Spicy Chicken Sandwich"
        - "Large French Fries • Large (500 Cal.)" -> "Large French Fries"
        """
        # Remove parenthetical suffixes like "(Beverages)", "(Individual Items)"
        item_name = re.sub(r'\s*\([^)]+\)\s*$', '', item_name)
        # Remove size/calorie info like "• Large (0 Cal.)"
        item_name = re.sub(r'\s*•.*', '', item_name)
        return item_name.strip()

    def _parse_nutrition_data(self, food_item: dict, source: str, restaurant_name: Optional[str] = None) -> Dict:
        """
        A helper function to parse and standardize nutrition data from a Nutritionix API response item.
        """
        return {
            'calories': food_item.get('nf_calories', 0) or 0,
            'protein': food_item.get('nf_protein', 0) or 0,
            'carbs': food_item.get('nf_total_carbohydrate', 0) or 0,
            'fat': food_item.get('nf_total_fat', 0) or 0,
            'fiber': food_item.get('nf_dietary_fiber', 0) or 0,
            'sugar': food_item.get('nf_sugars', 0) or 0,
            'sodium': food_item.get('nf_sodium', 0) or 0,
            'saturated_fat': food_item.get('nf_saturated_fat', 0) or 0,
            'name': food_item.get('food_name', ''),
            'brand': food_item.get('brand_name', restaurant_name),
            'serving_size': f"{food_item.get('serving_qty', 1)} {food_item.get('serving_unit', 'serving')}",
            'source': source,
        }

    def search_item(self, item_name: str, restaurant: str) -> Optional[dict]:
        """
        Searches for a single serving of an item using the Nutritionix instant search endpoint.
        This method is a fallback for when the natural language search fails.
        """
        clean_name = self.clean_item_name(item_name)
        cache_key = f"{restaurant.lower()}|{clean_name.lower()}"
        
        if cache_key in self.cache:
            print(f"✅ Cache hit for '{clean_name}' from '{restaurant}'")
            return self.cache[cache_key]
            
        print(f"🔍 Searching Nutritionix for: '{clean_name}' from '{restaurant}'")
        
        headers = {'x-app-id': self.app_id, 'x-app-key': self.app_key}
        
        search_queries = [
            f"{restaurant} {clean_name}",
            f"{clean_name} {restaurant}",
            clean_name,
        ]
        
        # Special handling for McDonald's possessive
        if "McDonald's" in restaurant:
            search_queries.insert(0, f"McDonalds {clean_name}")

        for query in search_queries:
            print(f"  Trying query: '{query}'")
            params = {
                'query': query,
                'branded': True,
                'common': False,
                'detailed': True  # Request detailed nutrition info to avoid a second API call
            }
            
            try:
                response = requests.get(self.instant_endpoint, headers=headers, params=params, timeout=self.timeout)
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

                data = response.json()
                branded_items = data.get('branded', [])
                
                if branded_items:
                    print(f"  Found {len(branded_items)} potential results for query '{query}'")
                    
                    best_match = None
                    best_score = 0
                    
                    for i, item in enumerate(branded_items[:10]):
                        brand = item.get('brand_name', '').lower()
                        name = item.get('food_name', '').lower()
                        nf_calories = item.get('nf_calories', 0)
                        
                        print(f"  {i+1}. {item['food_name']} - {item['brand_name']} ({nf_calories} cal)")
                        
                        score = 0
                        
                        if any(rest_part in brand for rest_part in ['mcdonald', 'mc donald']):
                            score += 10
                        
                        if clean_name.lower() == name:
                            score += 20
                        elif clean_name.lower() in name:
                            score += 10
                        
                        clean_words = set(clean_name.lower().split())
                        name_words = set(name.split())
                        matching_words = clean_words.intersection(name_words)
                        score += len(matching_words) * 3
                        
                        if 'spicy crispy chicken' in clean_name.lower() and 'crispy chicken' in name:
                            score += 5
                        if 'mcdouble' in clean_name.lower() and 'double' in name:
                            score += 3
                        
                        print(f"      Score: {score}")
                        
                        if score > best_score:
                            best_score = score
                            best_match = item
                    
                    if best_match and best_score >= 3:
                        print(f"✅ Best match: {best_match['food_name']} ({best_match['brand_name']}) - Score: {best_score}")
                        
                        # Parse the nutrition data directly from the search result to be more efficient
                        nutrition = self._parse_nutrition_data(best_match, 'nutritionix_search', restaurant)
                        
                        if nutrition:
                            self.cache[cache_key] = nutrition
                            self.save_cache()
                            return nutrition

            except requests.exceptions.RequestException as e:
                print(f"  ❌ API request failed for query '{query}': {e}")
                
        print(f"❌ No suitable match found for '{clean_name}' after trying all queries.")
        return None

    def get_nutrition_natural_language(self, item_name: str, restaurant: str, quantity: int) -> Optional[dict]:
        """
        Uses the more powerful Natural Language API to get nutrition for a specific quantity of an item.
        This is the preferred method.
        """
        clean_name = self.clean_item_name(item_name)
        query = f"{quantity} {clean_name} from {restaurant}"
        
        print(f"🗣️ Using Natural Language API with query: '{query}'")
        
        headers = {
            'x-app-id': self.app_id,
            'x-app-key': self.app_key,
            'Content-Type': 'application/json'
        }
        data = {'query': query}
        
        try:
            response = requests.post(self.nutrients_endpoint, headers=headers, json=data, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()
            foods = result.get('foods', [])
            
            if foods:
                food_item = foods[0] # Assume the first result is the best
                nutrition = self._parse_nutrition_data(food_item, 'nutritionix_natural', restaurant)
                print(f"✅ Found via Natural Language: {nutrition['calories']:.0f} cal, {nutrition['protein']:.1f}g protein")
                return nutrition

        except requests.exceptions.RequestException as e:
            print(f"❌ Natural Language API request failed: {e}")
        
        return None

    def get_nutrition_for_item(self, restaurant: str, item_name: str, quantity: int = 1) -> Optional[dict]:
        """
        Main method to get nutrition for an item. It tries the Natural Language API first,
        and falls back to the instant search API if needed. It also handles caching.
        """
        print(f"\n🍔 LOOKING UP: {quantity}x '{item_name}' from '{restaurant}'")
        clean_name = self.clean_item_name(item_name)
        
        # Use a cache key that includes quantity, as it affects the result
        cache_key = f"{restaurant.lower()}|{clean_name.lower()}|{quantity}"
        if cache_key in self.cache:
            print(f"✅ Cache hit for {quantity}x '{clean_name}'")
            return self.cache[cache_key]
        
        # --- Primary Strategy: Natural Language API ---
        # This is generally better as it can parse quantity and context together.
        nutrition = self.get_nutrition_natural_language(item_name, restaurant, quantity)
        
        # --- Fallback Strategy: Instant Search API ---
        if not nutrition:
            print("  -> Natural Language failed, falling back to Instant Search.")
            # Search for a single item first
            nutrition_single = self.search_item(item_name, restaurant)
            
            if nutrition_single:
                # If found, scale the nutrition by the quantity
                nutrition = nutrition_single.copy() # Create a copy to modify
                if quantity > 1:
                    for key in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sugar', 'sodium', 'saturated_fat']:
                        if key in nutrition:
                            nutrition[key] *= quantity
                    nutrition['source'] += '_scaled'
        
        if nutrition:
            # Cache the final result for the specific quantity
            self.cache[cache_key] = nutrition
            self.save_cache()
        
        return nutrition

def enhance_order_with_nutrition(order_data: dict) -> dict:
    """
    Main function to process a whole order, fetch nutrition for each item,
    and return the order data enhanced with totals and percentages.
    """
    print(f"\n{'='*20}\n🍎 STARTING NUTRITION LOOKUP 🍎\n{'='*20}")
    
    tracker = NutritionixTracker()
    enhanced_order = order_data.copy()
    restaurant = order_data.get('restaurant', 'Unknown Restaurant')
    items = order_data.get('items', [])
    
    print(f"🏪 Restaurant: {restaurant}")
    print(f"📦 Items to analyze: {len(items)}")
    
    meal_totals = {
        'total_calories': 0, 'total_protein': 0, 'total_carbs': 0, 'total_fat': 0,
        'total_fiber': 0, 'total_sugar': 0, 'total_sodium': 0, 'total_saturated_fat': 0
    }
    
    enhanced_items = []
    success_count = 0
    
    for i, item in enumerate(items, 1):
        item_name = item.get('name', 'Unknown Item')
        quantity = item.get('quantity', 1)
        
        nutrition = tracker.get_nutrition_for_item(restaurant, item_name, quantity)
        
        enhanced_item = item.copy()
        enhanced_item['nutrition'] = None

        if nutrition:
            success_count += 1
            enhanced_item['nutrition'] = nutrition
            
            # Add to meal totals
            for key in meal_totals:
                # e.g., key = 'total_calories', nutrition_key = 'calories'
                nutrition_key = key.replace('total_', '') 
                meal_totals[key] += nutrition.get(nutrition_key, 0)

            print(f"  -> SUCCESS: {nutrition['calories']:.0f} cal, {nutrition['protein']:.1f}g protein")
        else:
            print(f"  -> FAILED to find nutrition for '{item_name}'")
            
        enhanced_items.append(enhanced_item)
    
    # --- Final Summary ---
    enhanced_order['items'] = enhanced_items
    enhanced_order['meal_totals'] = meal_totals
    enhanced_order['nutrition_timestamp'] = datetime.now().isoformat()
    enhanced_order['nutrition_source'] = 'Nutritionix API'
    enhanced_order['success_rate'] = f"{success_count}/{len(items)}"
    
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
    
    print(f"\n{'='*50}\n📊 NUTRITION SUMMARY FOR {restaurant.upper()}\n{'='*50}")
    print(f"✅ Found nutrition for: {success_count} of {len(items)} items")
    print(f"🔥 Total Calories: {meal_totals['total_calories']:.0f}")
    print(f"🥩 Protein: {meal_totals['total_protein']:.1f}g ({meal_totals['macro_percentages']['protein']:.1f}%)")
    print(f"🍞 Carbs:   {meal_totals['total_carbs']:.1f}g ({meal_totals['macro_percentages']['carbs']:.1f}%)")
    print(f"🧈 Fat:     {meal_totals['total_fat']:.1f}g ({meal_totals['macro_percentages']['fat']:.1f}%)")
    print(f"🧂 Sodium:  {meal_totals['total_sodium']:.0f}mg")
    print(f"{'='*50}")
    
    return enhanced_order

# ==============================================================================
# Example Usage and Testing
# ==============================================================================
if __name__ == "__main__":
    
    # --- Mock DoorDash Order Data ---
    mock_order = {
        'restaurant': "McDonald's",
        'total': 25.50,
        'items': [
            {'name': 'McDouble', 'quantity': 1, 'price': 2.99},
            {'name': 'Spicy Crispy Chicken Sandwich', 'quantity': 1, 'price': 5.49},
            {'name': 'French Fries • Large (500 Cal.)', 'quantity': 2, 'price': 3.99},
            {'name': 'Diet Coke (Beverages)', 'quantity': 1, 'price': 1.99},
            {'name': 'An item that does not exist', 'quantity': 1, 'price': 10.00} # Test failure case
        ]
    }

    # Run the main function with the mock data
    final_order_data = enhance_order_with_nutrition(mock_order)

    # Pretty-print the final result
    # print("\n\n--- FINAL ENHANCED ORDER DATA ---")
    # print(json.dumps(final_order_data, indent=4))

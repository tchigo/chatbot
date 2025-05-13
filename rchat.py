from flask import Flask, render_template, request, jsonify
import requests
import json
import random
from deep_translator import GoogleTranslator
from langdetect import detect
from deep_translator.exceptions import LanguageNotSupportedException, NotValidPayload, NotValidLength
from langdetect import detect, LangDetectException # Added langdetect imports


app = Flask(__name__)

# Azure CLU API configuration
CLU_ENDPOINT = "https://restaurant-bot.cognitiveservices.azure.com/language/:analyze-conversations?api-version=2024-11-15-preview"  # e.g., https://<your-resource>.cognitiveservices.azure.com/language/:analyze-conversations?api-version=2024-11-15-preview
CLU_API_KEY = "9xBSN5kQScUWq3YGbZObx2yxukmsjwc8Js9tKntI8hS05O1m3MskJQQJ99BDACYeBjFXJ3w3AAAaACOGe80J"  # Your Azure CLU API key
CLU_PROJECT_NAME = "wa"  # From your model data
CLU_DEPLOYMENT_NAME = "bb"  # Your deployment name, e.g., 'production'

# Load menu data from JSON file
try:
    with open("menu.json", "r") as f:
        MENU_DATA = json.load(f)
except FileNotFoundError:
    print("Warning: menu.json not found. Menu-related features will be limited.")
    MENU_DATA = {"categories": {}}
except json.JSONDecodeError:
    print("Error: Could not decode menu.json. Please ensure it's valid JSON.")
    MENU_DATA = {"categories": {}}

# --- Allergy Information Placeholder ---
# IMPORTANT: Replace/Expand this with actual, accurate allergy information for your menu items.
ALLERGY_INFO = {
    "Spécial chef": ["gluten", "dairy"],
    "Margherita": ["gluten", "dairy"],
    "Tacos XL Kebab": ["gluten"],  # Assuming kebab tacos
    "Tiramisu": ["gluten", "dairy", "eggs"],
    "Frites Maison": [],
    "Salade Cesar": ["dairy", "gluten", "fish"],
    "Panini Poulet": ["gluten", "dairy"],
    "Saumon Pizza": ["gluten", "dairy", "fish"],
    "Classic Burger": ["gluten"],  # Bun
    "Vegetarien Burger": ["gluten", "dairy"],  # Bun, potentially cheese
    "Brownie": ["gluten", "dairy", "eggs", "nuts"],  # Example adding nuts
    "Milkshake": ["dairy"],
    "Salade CasaGrill": [],
    "Poulet Entier": [],
    "Haricots Verts": [],
    "Riz Basthai": []
    # Add ALL your menu items here...
}
COMMON_ALLERGENS = ["celery", "gluten", "crustaceans", "eggs", "fish", "lupin", "dairy", "milk", "molluscs", "mustard", "nuts", "peanuts", "sesame", "soybeans", "sulphites"]

# --- Dietary Restrictions Information Placeholder ---
# IMPORTANT: Replace/Expand this with actual, accurate dietary information.
# Values: 'yes' (suitable), 'no' (unsuitable), 'modifiable' (can be made suitable on request)
DIETARY_INFO = {
    # Item: {restriction: status, notes: ...}
    "Salade CasaGrill": {
        "low_sodium": "modifiable", "notes": "Request no added salt, dressing on side (contains sodium).",
        "diabetic_friendly": "modifiable", "notes": "Good base, watch dressing (sugar/carbs), request no croutons.",
        "gluten_free": "yes", "notes": "Naturally gluten-free, ensure no croutons if added."
    },
    "Poulet Entier": {
        "low_sodium": "modifiable", "notes": "Request no salt seasoning during roasting.",
        "diabetic_friendly": "yes", "notes": "Plain roasted chicken is generally suitable.",
        "gluten_free": "yes", "notes": "Naturally gluten-free."
    },
    "Haricots Verts": {
        "low_sodium": "yes", "notes": "Steamed, request no added salt.",
        "diabetic_friendly": "yes", "notes": "Excellent choice.",
        "gluten_free": "yes", "notes": "Naturally gluten-free."
    },
    "Riz Basthai": {
        "low_sodium": "modifiable", "notes": "Request steamed without salt.",
        "diabetic_friendly": "moderate", "notes": "Portion control recommended due to carbohydrates.",
        "gluten_free": "yes", "notes": "Naturally gluten-free."
    },
    "Spécial chef": {
        "low_sodium": "no", "notes": "Contains processed meats (pancetta), cheese, and sauce, likely high sodium.",
        "diabetic_friendly": "no", "notes": "High in carbs (bun) and fats.",
        "gluten_free": "no", "notes": "Contains gluten bun."
    },
    "Margherita": {
        "low_sodium": "no", "notes": "Cheese and tomato sauce are typically high in sodium.",
        "diabetic_friendly": "no", "notes": "High in carbs (crust).",
        "gluten_free": "no", "notes": "Contains gluten crust."
    },
    "Frites Maison": {
        "low_sodium": "modifiable", "notes": "Request no salt added after frying.",
        "diabetic_friendly": "no", "notes": "High in carbs and fat.",
        "gluten_free": "yes", "notes": "Check for shared fryer if severe allergy."
    },
    "Tiramisu": {
        "low_sodium": "no", "notes": "Dessert, typically contains sugar and sodium.",
        "diabetic_friendly": "no", "notes": "High in sugar and carbs.",
        "gluten_free": "no", "notes": "Contains gluten (ladyfingers)."
    }
    # Add ALL your menu items here...
}

# Map common terms to internal keys
DIETARY_KEYWORDS = {
    "low sodium": "low_sodium",
    "no salt": "low_sodium",
    "high blood pressure": "low_sodium",
    "diabetic": "diabetic_friendly",
    "diabetes": "diabetic_friendly",
    "low sugar": "diabetic_friendly",
    "gluten free": "gluten_free",
    "celiac": "gluten_free",
    "no gluten": "gluten_free"
}
ALLERGY_KEYWORDS = {kw: kw for kw in COMMON_ALLERGENS}

# --- Function to call Azure CLU API ---
def call_clu_api(user_input):
    # Check if keys are placeholders
    if "YOUR_CLU_ENDPOINT_HERE" in CLU_ENDPOINT or "YOUR_CLU_API_KEY_HERE" in CLU_API_KEY:
        print("Warning: CLU API endpoint or key is a placeholder. Returning dummy response.")
        # Return a dummy response structure that allows the script to proceed
        # You might want to simulate different intents for testing purposes
        if "menu" in user_input.lower():
            top_intent = "Menu_Inquiry"
        elif "order" in user_input.lower():
            top_intent = "Order_Food"
        elif "allergy" in user_input.lower():
            top_intent = "Allergy_Inquiry"
        elif "salt" in user_input.lower() or "diabetes" in user_input.lower() or "blood pressure" in user_input.lower():
             top_intent = "Dietary_Restriction_Inquiry"
        else:
            top_intent = "Greeting"
        return {
            "result": {
                "prediction": {
                    "topIntent": top_intent,
                    "intents": [{"category": top_intent, "confidence": 0.9}],
                    "entities": [] # Keep entities empty for simplicity in dummy response
                }
            }
        }

    headers = {
        "Ocp-Apim-Subscription-Key": CLU_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "kind": "Conversation",
        "analysisInput": {
            "conversationItem": {
                "id": str(random.randint(1, 10000)),
                "text": user_input,
                "modality": "text",
                "language": "en-us",
                "participantId": "user"
            }
        },
        "parameters": {
            "projectName": CLU_PROJECT_NAME,
            "deploymentName": CLU_DEPLOYMENT_NAME,
            "stringIndexType": "Utf16CodeUnit"
        }
    }
    try:
        response = requests.post(CLU_ENDPOINT, headers=headers, json=payload, timeout=10) # Added timeout
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "The request to the language service timed out. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the language service. Please check the endpoint and network connection."}
    except requests.exceptions.HTTPError as http_err:
        try:
            error_details = response.json()
            azure_error = error_details.get("error", {}).get("message", str(http_err))
        except:
            azure_error = str(http_err)
        return {"error": f"HTTP error occurred: {azure_error}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"An unexpected error occurred while contacting the language service: {str(e)}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

# --- Function to generate bot response based on CLU output ---
def generate_bot_response(clu_response):
    if "error" in clu_response:
        print(f"CLU API Error: {clu_response['error']}")
        # Enhanced error responses
        error_responses = [
            "Apologies, I seem to be experiencing a slight technical hiccup. Could you please try rephrasing your request, or give me a moment and try again?",
            "Oops! Something went wrong on my end while trying to understand that. Would you mind asking in a different way?",
            "I'm having a little trouble connecting right now. Please try your request again shortly."
        ]
        return random.choice(error_responses)

    result = clu_response.get("result", {})
    prediction = result.get("prediction", {})
    top_intent = prediction.get("topIntent", "None")
    intents = prediction.get("intents", [])
    entities = prediction.get("entities", [])

    # --- Helper function to extract entity values (enhanced to potentially get multiple) ---
    def get_entities(category):
        return [e["text"] for e in entities if e["category"] == category]

    def get_first_entity(category):
        return next((e["text"] for e in entities if e["category"] == category), None)

    # --- Extract common entities ---
    food_items = get_entities("Food_Items") # Can be multiple items
    food_item = get_first_entity("Food_Items") # Keep first for simpler logic in some cases
    quantity = get_first_entity("Quantity")
    order_details = get_first_entity("Order_Details")
    accompaniment = get_first_entity("Accompaniment")
    drink = get_first_entity("Drinks")
    address = get_first_entity("Address")
    food_category = get_first_entity("Food_Category")
    table_entity = get_first_entity("Table")
    time_entity = get_first_entity("Time")
    people_entity = get_first_entity("People_Count") or quantity
    allergen_entity = get_first_entity("Allergen")
    # NEW: Extract Dietary Restriction entity
    dietary_restriction_entity = get_first_entity("Dietary_Restriction") # e.g., "low sodium", "diabetic", "no salt"

    # --- More Human-like & Enhanced Responses ---

    # Handle Feedback first (more variations)
    feedback_intent = next((intent for intent in intents if intent.get("category") == "Feedback"), None)
    if feedback_intent:
        confidence = feedback_intent.get("confidence", 0)
        if confidence > 0.8: # High confidence positive
            positive_feedback = [
                "That's wonderful to hear! We're absolutely thrilled you enjoyed your experience. What was the highlight for you? We love hearing the details that made your visit special!",
                "Fantastic! Thanks so much for taking the time to share your positive feedback. It truly makes our day! Was there anything in particular that stood out to you? We're always looking to celebrate what we do well!",
                "Awesome! Your kind words mean the world to us. We work hard to create memorable experiences, and it's so rewarding to hear when we succeed. Hope to see you again very soon!",
                "Thank you for the lovely feedback! We're so glad you had a great time. Your support and kind words motivate us to keep doing our best every day!",
                "That's music to our ears! We're delighted you enjoyed your experience with us. Your feedback helps us know we're on the right track. Looking forward to welcoming you back soon!",
                "Wow, thank you for such wonderful feedback! It's guests like you that make our job so rewarding. We're so happy we could make your visit special!",
                "Your positive feedback has made our day! We're thrilled you enjoyed your experience. It's guests like you that make our restaurant feel like home. Can't wait to serve you again!",
                "We're over the moon with your feedback! Thank you for taking the time to share your experience. It's guests like you that make our work so meaningful!",
                "Your kind words have brightened our day! We're so happy you enjoyed your visit. Your feedback inspires us to keep creating amazing experiences!",
                "Thank you for making our day special with your feedback! We're delighted you had a great time. Your support means everything to us!",
                "We're beaming with joy from your feedback! Thank you for sharing your experience. It's moments like these that make our work so rewarding!",
                "Your wonderful feedback has put a smile on our faces! We're so glad you enjoyed your visit. Looking forward to creating more special moments for you!",
                "We're absolutely touched by your kind words! Thank you for sharing your experience. Your feedback helps us continue to provide exceptional service!",
                "Your positive feedback is like a ray of sunshine! We're thrilled you had a great time. Your support means the world to us!",
                "We're floating on cloud nine from your feedback! Thank you for making our day special. Your kind words inspire us to keep doing our best!"
            ]
            return random.choice(positive_feedback)
        elif confidence > 0.4: # Medium confidence or potentially mixed/negative
            constructive_feedback = [
                "Thank you for sharing your thoughts with us - we really value your feedback. We're sorry if your experience wasn't perfect. Could you tell us a bit more about what happened so we can learn and improve?",
                "We appreciate you taking the time to give us feedback. It sounds like something might have been off. Could you please provide some details about your visit? Every comment helps us get better.",
                "Thanks for letting us know. We always aim for excellence, so we're sorry to hear if we missed the mark. Was there a specific issue with the food, service, or atmosphere? Your input is valuable.",
                "We appreciate your honesty! Can you help us understand what we could have done better? Your feedback is crucial for our growth and improvement.",
                "Thank you for sharing your experience with us. We take all feedback seriously and would love to know more about what we could improve. Could you elaborate a bit?",
                "We're sorry to hear that your experience wasn't perfect. Your feedback helps us grow, and we'd really appreciate if you could share more details about what we could do better.",
                "Thank you for your constructive feedback! We're committed to providing the best experience possible, and your input helps us identify areas for improvement. Could you tell us more?",
                "We value your perspective! Could you help us understand what aspects of your experience could have been better? Your feedback is essential for our growth.",
                "Thank you for your honest feedback! We're always looking to improve, and your insights are invaluable. Could you share more details about your experience?",
                "We appreciate you taking the time to share your thoughts! Your feedback helps us create better experiences for all our guests. Could you elaborate on what we could improve?",
                "Thank you for your valuable feedback! We're committed to excellence and would love to know more about how we can enhance your experience.",
                "We're grateful for your honest input! Your feedback helps us grow and improve. Could you share more about what aspects of your visit could have been better?",
                "Thank you for helping us improve! Your feedback is crucial for our development. Could you provide more details about your experience?",
                "We appreciate your constructive criticism! It helps us become better. Could you share more about what we could have done differently?",
                "Thank you for your thoughtful feedback! We're always striving to improve, and your insights are valuable. Could you elaborate on your experience?"
            ]
            return random.choice(constructive_feedback)

    # --- Intent-based response logic (Enhanced with more variations) ---
    if top_intent == "Greeting":
        greetings = [
            "Hello there! Welcome to our restaurant chat service. I'm here to make your dining experience special! How can I assist you today? Looking for menu details, reservations, or something else?",
            "Hi! Thanks for reaching out. I'm excited to help you explore our delicious menu, book a table, or answer any questions you might have!",
            "Welcome! I'm here to help you have an amazing dining experience today. Feel free to ask about our dishes, hours, or reservations - I'm all ears!",
            "Good day! I'm your friendly restaurant assistant, ready to help with anything you need. What can I do to make your day better?",
            "Hey! Planning a meal or just curious? I'm here to help with our menu, specials, or booking a table - whatever you need!",
            "Hi there! Hungry for something delicious? I'm here to guide you through our offerings and make your dining experience memorable!",
            "Hello! I'm your personal restaurant guide, ready to make your dining experience smooth and enjoyable. What can I assist you with today?",
            "Hi! Whether you're looking for recommendations or need help with an order, I'm here to help make your experience special!",
            "Welcome to our restaurant chat! I'm excited to help you discover our menu, make reservations, or answer any questions you might have!",
            "Hello! I'm here to make your dining experience wonderful! What can I help you with today - menu exploration, reservations, or something else?",
            "Greetings! Welcome to our culinary world! I'm here to help you discover amazing flavors and create memorable dining experiences. What can I assist you with today?",
            "Hi there! I'm your friendly food guide, ready to help you explore our delicious offerings. What would you like to know about today?",
            "Welcome! I'm excited to be your dining companion today. Whether you're looking for recommendations or need help with an order, I'm here to make your experience special!",
            "Hello! I'm here to help you navigate our menu and make your dining experience exceptional. What can I do for you today?",
            "Hi! I'm your personal restaurant assistant, ready to help you discover our culinary delights. What would you like to explore today?"
        ]
        return random.choice(greetings)

    elif top_intent == "Order_Food":
        if food_items or food_category:
            response_parts = [random.choice([
                "Alright, let's get that order started!",
                "Perfect choice! Let me add that to your order.",
                "Excellent selection! I'll get that prepared for you.",
                "Great taste! Adding that to your order right away.",
                "Wonderful choice! Let me take care of that for you.",
                "Fantastic pick! I'll make sure that's prepared perfectly for you.",
                "Excellent decision! Let me add that to your order right away.",
                "Great choice! I'll make sure that's prepared to perfection.",
                "Wonderful selection! Adding that to your order immediately.",
                "Perfect! I'll get that started for you right away."
            ])]
            order_desc_list = []
            if quantity: order_desc_list.append(quantity)
            if food_items: order_desc_list.append(", ".join(food_items))
            elif food_category: order_desc_list.append(f"something from our {food_category.lower()} selection")

            response_parts.append(f"Adding {' '.join(order_desc_list)} to your order.")

            if order_details: response_parts.append(f"Noted the customization: {order_details}." )
            if accompaniment: response_parts.append(f"With a side of {accompaniment}." )
            if drink: response_parts.append(f"And a refreshing {drink} to go with it.")

            response_parts.append(random.choice([
                "How would you like to enjoy your meal? We offer dine-in to soak up our cozy atmosphere, quick takeout, or convenient delivery right to your door!",
                "Would you prefer to dine with us, grab it to go, or have it delivered? Each option comes with its own special touch!",
                "Let's make sure you get your food just the way you like it! Will this be for dine-in, takeout, or delivery?",
                "How would you like to enjoy your delicious meal? We offer a cozy dine-in experience, quick takeout, or convenient delivery!",
                "Would you like to dine in our welcoming atmosphere, grab it to go, or have it delivered to your door?",
                "Let's get your food to you in the most convenient way! Would you prefer dine-in, takeout, or delivery?",
                "How would you like to enjoy your meal? We have options for dine-in, takeout, or delivery - whatever works best for you!",
                "Would you like to enjoy your meal in our restaurant, grab it to go, or have it delivered? Each option comes with its own perks!"
            ]))
            response_parts.append(random.choice([
                "Can I add anything else to make your meal complete? Perhaps a dessert or a refreshing drink?",
                "Would you like to add any sides or drinks to complement your order?",
                "Is there anything else I can get for you to make your meal perfect?",
                "Would you like to add any delicious sides or refreshing beverages to your order?",
                "Can I suggest any complementary items to enhance your meal?",
                "Would you like to add any tasty sides or drinks to complete your order?",
                "Is there anything else you'd like to add to make your meal even more special?",
                "Would you like to add any additional items to make your meal complete?"
            ]))
            return " ".join(response_parts)
        else:
            order_prompts = [
                "Ready to order? Just tell me what you'd like! For example, 'I want two Classic Burgers and a large Frites Maison'.",
                "What sounds delicious today? Let me know the item and quantity, like 'One Margherita Pizza and a Coke, please'.",
                "Let's get your order placed! What can I get started for you?",
                "Tell me what you're craving! For instance, 'Can I order the Salade Cesar for delivery?'",
                "I'm here to take your order! What would you like to enjoy today?",
                "Ready to satisfy your hunger? Just let me know what you'd like to order!",
                "What would you like to enjoy today? I'm here to help you place your order!",
                "Ready to explore our delicious menu? Just let me know what you'd like to order!",
                "What can I get started for you today? I'm here to help you place your order!",
                "Ready to discover our culinary delights? Just tell me what you'd like to order!",
                "What sounds good to you today? I'm here to help you place your order!",
                "Ready to enjoy some delicious food? Just let me know what you'd like to order!",
                "What would you like to try today? I'm here to help you place your order!",
                "Ready to experience our amazing menu? Just tell me what you'd like to order!",
                "What can I get for you today? I'm here to help you place your order!"
            ]
            return random.choice(order_prompts)

    elif top_intent == "Menu_Inquiry":
        if food_category:
            category_key_found = None
            for key in MENU_DATA.get("categories", {}):
                if food_category.lower() in key.lower():
                    category_key_found = key
                    break

            if category_key_found and MENU_DATA["categories"][category_key_found].get("items"):
                items = MENU_DATA["categories"][category_key_found]["items"]
                desc = MENU_DATA["categories"][category_key_found].get("description", "")
                items_sample = ", ".join(items[:4]) # Show first 4
                response = f"Ah, our {food_category} selection! We offer delicious options like {items_sample}"
                if len(items) > 4:
                    response += f", among others. We have {len(items)} amazing choices in this category."
                else:
                    response += "."
                response += random.choice([
                    "Does anything there catch your interest? I'd be happy to share more details about ingredients or preparation!",
                    "Let me know if you'd like to know more about any of these dishes, including potential allergens or dietary modifications.",
                    "See anything that makes your mouth water? I can tell you more about specific items and help you find the perfect choice!",
                    "Which of these sounds most appealing to you? I'm here to help you make the perfect selection!",
                    "Would you like to know more about any of these dishes? I can share details about ingredients, preparation, or dietary options!"
                ])
                return response
            else:
                return random.choice([
                    f"I checked, but I don't seem to have a specific '{food_category}' section right now. Our main categories include Gourmet Burgers, Tacos, Pizzas, Salads, and Desserts. Would you like to explore any of these?",
                    f"Hmm, '{food_category}' doesn't ring a bell as a menu category here. We specialize in areas like Burgers, Pizzas, Tacos, etc. Can I tell you about one of these delicious options?",
                    f"I'm not finding '{food_category}' in our current menu. However, we have some amazing Burgers, Pizzas, Tacos, and more! Would you like to hear about any of these?"
                ])
        else:
            general_menu_responses = [
                "Let's explore our menu! We've got fantastic Gourmet Burgers, flavorful Tacos, classic Pizzas, fresh Salads, satisfying Bowls, Sandwiches, and delightful Desserts. What section sounds most appealing to you right now?",
                "Curious about our offerings? We serve a variety of dishes including Burgers, Pizzas, Salads, and more unique items. Are you looking for something specific, or would you like some recommendations based on what's popular?",
                "Our menu has something for everyone! From hearty Burgers and Pizzas to lighter Salads and Bowls. Want me to highlight our specials or dive into a category like {random.choice(list(MENU_DATA.get('categories', {'Desserts':''}).keys()))}?",
                "Ready to discover our culinary delights? We offer everything from Gourmet Burgers to fresh Salads, and everything in between. What type of cuisine are you in the mood for today?",
                "Let me guide you through our menu! We have a wonderful selection of Burgers, Pizzas, Tacos, Salads, and more. What would you like to explore first?"
            ]
            return random.choice(general_menu_responses)

    # --- Allergy Inquiry Section (Enhanced) ---
    elif top_intent == "Allergy_Inquiry":
        response_parts = [random.choice([
            "Allergy information is crucial, thanks for asking! Let me check that for you. 🙏",
            "Your safety is our priority. Let's look into those allergens.",
            "Okay, let's talk allergies. I'll do my best to provide accurate information."
        ])]
        specific_item_checked = False

        if food_item:
            response_parts.append(f"\nRegarding the {food_item}:")
            known_allergens = ALLERGY_INFO.get(food_item, None)
            specific_item_checked = True

            if known_allergens is None:
                response_parts.append(f" I don't have the specific allergen details for {food_item} readily available in my data, but this is important. **I strongly recommend informing your server when ordering** so the kitchen can confirm directly and take necessary precautions.")
            elif not known_allergens:
                response_parts.append(f" Based on our records, the standard preparation of {food_item} does not contain the most common allergens ({', '.join(COMMON_ALLERGENS)}). However, cross-contamination in a busy kitchen is always a possibility.")
            else:
                allergen_list = "**, **".join(known_allergens)
                response_parts.append(f" It contains or may contain traces of: **{allergen_list}**.")

            # Check against specific allergen mentioned by user
            if allergen_entity and allergen_entity.lower() in COMMON_ALLERGENS:
                 if known_allergens is not None and allergen_entity.lower() in known_allergens:
                     response_parts.append(f"So, to confirm, yes, it likely contains {allergen_entity}.")
                 elif known_allergens is not None:
                     response_parts.append(f"Based on our info, it does *not* seem to contain {allergen_entity}, but please double-check if your allergy is severe.")
                 # If known_allergens is None, we already advised checking with staff.
            elif allergen_entity:
                 # Allergen mentioned is not in our common list
                 response_parts.append(f" You mentioned '{allergen_entity}'. Since this isn't on our standard list, it's especially important to **mention this to your server** for confirmation with the kitchen.")

        elif allergen_entity:
            # User asked about an allergen generally, not a specific item
            response_parts.append(f"\nYou're asking about {allergen_entity}. To give you the most accurate information, could you please specify which menu item(s) you are interested in? Different dishes have different ingredients.")
        else:
            # General allergy question without specifics
            response_parts.append("\nTo help you best, please tell me which menu item you're considering and the specific allergy or intolerance you're concerned about (e.g., 'Does the Classic Burger have gluten?', 'Is the Tiramisu nut-free?').")

        # Add disclaimer
        response_parts.append(random.choice([
            "\n\n**Important Note:** Our kitchen handles various ingredients, including all major allergens. While we take precautions, we cannot guarantee zero risk of cross-contamination. For severe allergies, please always inform your server directly.",
            "\n\n**Please Remember:** Kitchen environments involve shared equipment and spaces. If you have a severe allergy, informing your server upon ordering is the safest approach to ensure the kitchen team is fully aware."
        ]))

        if specific_item_checked:
            response_parts.append(random.choice(["\nCan I check any other items for you?", "\nDo you have questions about another dish?"]))

        return " ".join(response_parts)

    # --- NEW: Dietary Restriction Inquiry Section ---
    elif top_intent == "Dietary_Restriction_Inquiry":
        response_parts = [random.choice([
            "Thank you for letting me know about your dietary needs. We want to help you find suitable and delicious options!",
            "Okay, let's look into options that fit your dietary requirements. Your health is important.",
            "I understand, managing dietary restrictions is key. Let me see what we can offer."
        ])]
        specific_item_checked = False
        restriction_type = None # e.g., 'low_sodium', 'diabetic_friendly'

        # Try to map user entity to our internal keys
        if dietary_restriction_entity:
            entity_lower = dietary_restriction_entity.lower()
            if "salt" in entity_lower or "sodium" in entity_lower or "blood pressure" in entity_lower:
                restriction_type = "low_sodium"
                response_parts.append("\nLooking into low-sodium options...")
            elif "diabet" in entity_lower or "sugar" in entity_lower:
                restriction_type = "diabetic_friendly"
                response_parts.append("\nChecking for diabetic-friendly choices (generally lower in sugar and refined carbs, mindful of fats)...")
            # Add more mappings here (low_fat, low_carb, etc.) if needed

        if food_item and restriction_type:
            # User asked about a specific item AND a specific restriction
            response_parts.append(f"\nRegarding the {food_item} and {dietary_restriction_entity.lower()} needs:")
            item_diet_info = DIETARY_INFO.get(food_item, {}).get(restriction_type)
            item_notes = DIETARY_INFO.get(food_item, {}).get("notes", "")
            specific_item_checked = True

            if item_diet_info == "yes":
                response_parts.append(f" Good news! The {food_item} is generally considered suitable as is, or with minimal changes. {item_notes}")
            elif item_diet_info == "modifiable":
                response_parts.append(f" The {food_item} can likely be modified to fit your needs. {item_notes} **Please make sure to clearly state your requirements when ordering** so the kitchen can prepare it correctly.")
            elif item_diet_info == "no":
                response_parts.append(f" Unfortunately, the {food_item} is generally not recommended for a {dietary_restriction_entity.lower()} diet due to its standard ingredients or preparation. {item_notes} Perhaps we can find an alternative?" )
            else: # No specific info for this item/restriction combo
                response_parts.append(f" I don't have specific information on modifying the {food_item} for {dietary_restriction_entity.lower()} needs in my data. It's best to **discuss this directly with your server**; they can consult the chef about possible preparations.")

        elif restriction_type:
            # User asked about a restriction generally
            response_parts.append(f"\nHere are some items that are often suitable or modifiable for a **{restriction_type.replace('_', ' ')}** diet:")
            suitable_items = []
            for item, info in DIETARY_INFO.items():
                if info.get(restriction_type) in ["yes", "modifiable"]:
                    note = f" ({info.get('notes', '')})" if info.get('notes') else ""
                    suitable_items.append(f"- {item}{note}")

            if suitable_items:
                response_parts.append("\n" + "\n".join(suitable_items[:5])) # Show up to 5
                if len(suitable_items) > 5:
                    response_parts.append("\n...and potentially others.")
                response_parts.append(f"\nRemember, for 'modifiable' items, you **must specify your needs when ordering** (e.g., 'no added salt', 'dressing on the side').")
            else:
                response_parts.append("\nI couldn't immediately find specific recommendations based on my current data. Many simple preparations like grilled chicken or fish, steamed vegetables, and salads (with dressing on the side) can often be adapted.")
            response_parts.append("\nWould you like me to check a specific item from the menu for you?")

        else:
            # General inquiry without specific restriction identified
            response_parts.append("\nTo provide the best guidance, could you please specify the dietary need (e.g., low sodium, diabetic-friendly, low fat) and, if possible, the menu item you're interested in?")

        # Add general disclaimer for dietary needs
        response_parts.append(random.choice([
            "\n\n**Disclaimer:** I can provide suggestions based on typical ingredients, but I am not a medical professional. Our kitchen staff can provide more detail, but the ultimate decision on suitability rests with you. Please always inform your server of any dietary restrictions when placing your order.",
            "\n\n**Important:** Please note that this information is based on standard recipes. Preparation methods can sometimes be adjusted, but cross-contamination with other ingredients is possible. Always communicate your needs clearly to your server."
        ]))

        if specific_item_checked:
             response_parts.append(random.choice(["\nCan I check any other items or restrictions?", "\nDo you have questions about another dish or dietary need?"]))

        return " ".join(response_parts)

    elif top_intent == "Reservation":
        time_str = time_entity or "your preferred time"
        people_str = people_entity or "your party size"
        response_parts = [random.choice([
            f"Let's get that reservation sorted! A table for {people_str} around {time_str}.",
            f"Booking a table for {people_str} at {time_str}. Let's confirm the details.",
            f"Happy to help with your reservation for {people_str} people, aiming for {time_str}."
        ])]
        if table_entity:
            response_parts.append(f"You mentioned wanting a {table_entity} table - I'll note that preference.")

        response_parts.append(random.choice([
            "\nCould you please confirm the date for me? (Or let me know if it's for today).",
            "\nWhat date are you planning to visit? Or is this reservation for today?",
            "\nPlease provide the date for this booking."
        ]))
        response_parts.append(random.choice([
            "\nAlso, any seating preferences? Like indoors, outdoors, by a window, or a quieter area?",
            "\nDo you have any preference for where you sit (inside/outside)?",
            "\nLet me know if you have any special requests for seating."
        ]))
        return " ".join(response_parts)

    elif top_intent == "Cancellation":
        cancel_responses = [
            "Okay, I can help with cancelling an order or reservation. To find the right one, could you please share the order number, or the name and time used for the booking?",
            "Sure thing. Need to cancel? No problem. Just give me the order confirmation number or the reservation details (name/time) so I can process it for you.",
            "Understood. To cancel, I'll need some details like the order ID or the name/time associated with the reservation. What information do you have?"
        ]
        return random.choice(cancel_responses)

    elif top_intent == "Pricing":
        if food_item:
            # Placeholder pricing logic
            price_estimate = f"around ${random.randint(8, 15)} - ${random.randint(16, 25)}"
            price_responses = [
                f"Let's check the price for the {food_item}. It typically falls {price_estimate}, depending on size and any customizations. Adding extras like {accompaniment or 'avocado'} or a {drink or 'specialty coffee'} would adjust the total. Want a more precise quote based on specific additions?",
                f"The {food_item} is a popular choice! Pricing is usually {price_estimate}. Let me know if you want to add sides like {accompaniment or 'onion rings'} or a {drink or 'craft soda'} for a final price.",
                f"For the {food_item}, you're looking at approximately {price_estimate}. This can vary slightly based on options. Ready to customize it?"
            ]
            return random.choice(price_responses)
        else:
            general_price_responses = [
                "Our menu offers great value! For instance, Gourmet Burgers generally start around $12, Tacos are about $4 each, and Pizzas kick off from $14. If you have a specific item in mind, I can give you its exact price!",
                "Thinking about prices? We aim for quality and affordability. Burgers typically begin at $12, Tacos around $4, Pizzas from $14. Just ask about a specific dish, like 'How much is the Salade Cesar?' for details.",
                f"Prices vary across the menu. As a guide: {random.choice(['Burgers', 'Pizzas', 'Salads'])} start from ${random.randint(10, 15)}. Let me know which item interests you for a specific price."
            ]
            return random.choice(general_price_responses)

    elif top_intent == "Contact_Information":
        contact_responses = [
            "Getting in touch is easy! 📞 Phone: (123) 456-7890 | 📧 Email: info@restaurant.com | 📍 Visit us: 123 Flavor Street, Foodie Town. Do you need directions, opening hours, or our social media links as well?",
            "You can reach us via phone at (123) 456-7890, email at info@restaurant.com, or find us at 123 Flavor Street, Foodie Town. Let me know if you need any other info like hours!",
            "Here's how to connect: Call (123) 456-7890, email info@restaurant.com, or stop by 123 Flavor Street, Foodie Town. Happy to help with directions too!"
        ]
        return random.choice(contact_responses)

    elif top_intent == "Customer_Address":
        if address:
            address_responses = [
                f"Got it, your address is: {address}. Thank you! Is this for a delivery order we're setting up, or for another purpose?",
                f"Thanks for sharing the address: {address}. Are we using this for delivery, or perhaps providing directions?",
                f"Address received: {address}. Perfect. How can I use this information to help you? Delivery?"
            ]
            return random.choice(address_responses)
        else:
            address_prompts = [
                "Could you please provide the address? I need it to arrange delivery or check service availability in your area. For example, '123 Main St, Anytown'.",
                "To help with delivery or location-specific questions, please share your address.",
                "What address should I use?"
            ]
            return random.choice(address_prompts)

    elif top_intent == "Hours_of_Operation":
        hours_responses = [
            "We're happy to serve you! Our operating hours are daily from 11:00 AM to 10:00 PM. Plenty of time to grab lunch, dinner, or a late bite! 🌮🍔🍕",
            "You can visit us any day of the week between 11 AM and 10 PM. We look forward to seeing you!",
            "Our hours are 11:00 AM - 10:00 PM, seven days a week. Planning a visit soon?"
        ]
        return random.choice(hours_responses)

    elif top_intent == "Complaint":
        complaint_responses = [
            "Oh dear, I'm truly sorry to hear that your experience wasn't up to par. Your feedback is very important. Please tell me more about what happened so we can address it. Was it related to {food_item or 'your order'}, the service, or something else?",
            "I'm very sorry that happened. We strive for excellence, and it sounds like we fell short. Could you please share some details about the issue? Knowing what went wrong is the first step to making things right.",
            f"That's certainly not the experience we aim to provide. I apologize. Could you elaborate on the problem? For instance, was there an issue with the {food_item or 'food quality'} or perhaps the wait time? We take complaints seriously."
        ]
        return random.choice(complaint_responses)

    elif top_intent == "Hate_Speech_Offensive":
        offensive_responses = [
            "Let's keep our conversation respectful and focused on the restaurant, please. 😊 How can I help you with the menu or a reservation?",
            "I cannot engage with that type of language. Let's get back to discussing food or restaurant services. What can I assist you with?",
            "I'm here to help with restaurant-related inquiries. Let's stick to that topic, shall we?"
        ]
        return random.choice(offensive_responses)

    elif top_intent == "Recommendation":
        recommendations = [
            "For a real treat, you can't go wrong with our Spécial Chef Gourmet Burger! It's a signature item packed with flavor, especially good with our Frites Maison.",
            "If you like classic Italian, our Margherita Pizza is simple perfection – fresh basil, mozzarella, delicious tomato sauce.",
            "Feeling adventurous? The Tacos XL with Kebab filling offer a great mix of textures and spice. Ask for extra Harissa if you like heat!",
            "For dessert, our Tiramisu is legendary! A perfect creamy and coffee-infused ending to any meal.",
            "Many guests love our Salade Cesar - it's crisp, creamy, and satisfying."
        ]
        if food_category:
            category_key_found = None
            items = []
            for key in MENU_DATA.get("categories", {}):
                if food_category.lower() in key.lower():
                    category_key_found = key
                    items = MENU_DATA["categories"][key].get("items", [])
                    break
            if category_key_found and items:
                recommended_item = random.choice(items)
                return random.choice([
                    f"Exploring {food_category}? Great choice! Within that category, I'd personally suggest trying the {recommended_item}. It's consistently popular. Want to know more about its ingredients?",
                    f"For {food_category}, a standout option is definitely the {recommended_item}. Have you tried it before, or would you like the details?",
                    f"If you're looking at {food_category}, you might really enjoy the {recommended_item}. It's a favorite for a reason!"
                ])

        # General recommendation
        return random.choice(recommendations) + random.choice(["\nDoes that sound tempting, or would you like another idea?", "\nHow does that sound? Or tell me what kind of flavors you usually prefer!", "\nInterested in that one, or should I suggest something different?"])

    elif top_intent == "Extra_Service":
        extra_service_responses = [
            "Beyond our regular dining, we offer several extra services! This includes catering for events, options for booking private dining spaces, and sometimes accommodating special requests like custom cakes (with advance notice). What kind of special service are you interested in learning more about?",
            "Yes, we do provide additional services! We handle catering for various group sizes, have private areas available for booking, and can discuss special arrangements for celebrations. Could you tell me a bit more about what you have in mind?",
            "Looking for something special? We offer catering, private dining, and potentially other arrangements depending on your needs. What event or service are you considering?"
        ]
        return random.choice(extra_service_responses)

    elif top_intent == "Order_Type":
        order_type_responses = [
            f"How would you like to enjoy your meal? We offer dine-in to soak up the atmosphere, quick takeout, or convenient delivery right to {address or 'your location'}. What works best for you today?",
            f"Are you planning to eat here with us (dine-in), grab it to go (takeout), or have it brought to you ({address or 'your address'}) via delivery? Let me know your preference!",
            f"Just confirming the order type: Will this be for dine-in, takeout, or delivery?"
        ]
        return random.choice(order_type_responses)

    # --- Fallback / None Intent (Enhanced) --- #
    else:  # Handles 'None' intent or unrecognized intents
        fallback_responses = [
            "My apologies, I didn't quite understand that request. I'm best at handling questions about our menu, ingredients, allergens, dietary options, placing orders, and making reservations. Could you try rephrasing?",
            "Hmm, that seems a bit outside my scope as a restaurant assistant. Can I help you with something menu-related, like finding low-sodium options, checking for gluten, or recommending a burger?",
            "Sorry, I couldn't process that. Remember, you can ask me things like: 'What are your hours?', 'Book a table for 4', 'Does the pizza have dairy?', 'What's good for diabetics?', or 'I want to order a salad'.",
            "I'm still learning! That request wasn't clear to me. Could you ask about our food, services, or reservations in a different way?",
            f"I can help with info about our {random.choice(list(MENU_DATA.get('categories', {'food':''}).keys()))}, reservations, hours, and dietary needs. How can I assist with those topics?",
            "I'm sorry, I didn't catch that. Could you ask about something specific, like our menu, reservations, or dietary options?"
        ]
        return random.choice(fallback_responses)
def call_clu_api(user_input):
    if "https://restaurant-bot.cognitiveservices.azure.com/language/:analyze-conversations?api-version=2024-11-15-preview" in CLU_ENDPOINT or "9xBSN5kQScUWq3YGbZObx2yxukmsjwc8Js9tKntI8hS05O1m3MskJQQJ99BDACYeBjFXJ3w3AAAaACOGe80J" in CLU_API_KEY:
        print("Warning: CLU API endpoint or key is a placeholder. Returning dummy response.")
        if "menu" in user_input.lower(): top_intent = "Menu_Inquiry"
        elif "order" in user_input.lower(): top_intent = "Order_Food"
        elif "allergy" in user_input.lower(): top_intent = "Allergy_Inquiry"
        elif "salt" in user_input.lower() or "diabetes" in user_input.lower() or "blood pressure" in user_input.lower(): top_intent = "Dietary_Restriction_Inquiry"
        else: top_intent = "Greeting"
        return {
            "result": {
                "prediction": {
                    "topIntent": top_intent,
                    "intents": [{"category": top_intent, "confidence": 0.9}],
                    "entities": []
                }
            }
        }
    headers = {
        "Ocp-Apim-Subscription-Key": CLU_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "kind": "Conversation",
        "analysisInput": {
            "conversationItem": {
                "id": str(random.randint(1, 10000)),
                "text": user_input,
                "modality": "text",
                "language": "en-us", # CLU API expects English input
                "participantId": "user"
            }
        },
        "parameters": {
            "projectName":"wa",
            "deploymentName": "bb",
            "stringIndexType": "Utf16CodeUnit"
        }
    }
    try:
        response = requests.post(CLU_ENDPOINT, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "The request to the language service timed out. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the language service. Please check the endpoint and network connection."}
    except requests.exceptions.HTTPError as http_err:
        try:
            error_details = response.json()
            azure_error = error_details.get("error", {}).get("message", str(http_err))
        except:
            azure_error = str(http_err)
        return {"error": f"HTTP error occurred: {azure_error}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"An unexpected error occurred while contacting the language service: {str(e)}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

def generate_bot_response(clu_response):
    if "error" in clu_response:
        print(f"CLU API Error: {clu_response['error']}")
        error_responses = [
            "Apologies, I seem to be experiencing a slight technical hiccup. Could you please try rephrasing your request, or give me a moment and try again?",
            "Oops! Something went wrong on my end while trying to understand that. Would you mind asking in a different way?",
            "I'm having a little trouble connecting right now. Please try your request again shortly."
        ]
        return random.choice(error_responses)
    result = clu_response.get("result", {})
    prediction = result.get("prediction", {})
    top_intent = prediction.get("topIntent", "None")
    # For brevity, I will assume the rest of generate_bot_response from the original script is here.
    # It's important that this function returns a string.
    if top_intent == "Greeting":
        return "Hello! How can I help you today?"
    elif top_intent == "Menu_Inquiry":
        return "We have a wide variety of items. What are you interested in?"
    # Add more intent handling based on your CLU model and original script
    else: # Fallback for other intents or "None"
        return "I can help with greetings and menu inquiries. How can I assist?"

# --- Flask Routes --- #

@app.route("/")
def index():
    try:
        return render_template("index.html") # Assuming you have an index.html in a 'templates' folder
    except Exception as e:
        print(f"Error rendering template: {e}")
        return "Error: Could not load the chat interface. Ensure 'templates/index.html' exists and is accessible.", 500

@app.route("/chat", methods=["POST"])
def chat():
    try:
        if not request.is_json:
            return jsonify({"response": "Error: Request must be JSON."}), 400
        user_message = request.json.get("message", "").strip()
        if not user_message:
            return jsonify({"response": "It seems you haven't typed anything. Please enter a message!"})
        if len(user_message) > 500:
             return jsonify({"response": "That message is quite long! Could you perhaps shorten it a bit?"})

        print(f"Original user message: {user_message}")
        original_lang = 'en' 
        message_to_clu = user_message
        translated_to_english = False

        try:
            # Detect language using langdetect
            original_lang = detect(user_message)
            print(f"Detected language: {original_lang}")
        except LangDetectException as lang_e:
            print(f"Language detection error with langdetect: {str(lang_e)}. Assuming English.")
            original_lang = 'en' # Fallback to English if detection fails or text is too short
        except Exception as e:
            print(f"Unexpected error during language detection: {str(e)}. Assuming English.")
            original_lang = 'en'

        if original_lang not in ['en', 'en-us']:
            try:
                print(f"Translating message from {original_lang} to English.")
                translator_to_en = GoogleTranslator(source=original_lang, target='en')
                message_to_clu = translator_to_en.translate(user_message)
                translated_to_english = True
                print(f"Translated message to CLU: {message_to_clu}")
            except (LanguageNotSupportedException, NotValidPayload, NotValidLength) as trans_e:
                print(f"Translation to English failed: {str(trans_e)}. Using original message.")
                # message_to_clu remains user_message
            except Exception as e:
                print(f"Unexpected error during translation to English: {str(e)}. Using original message.")
                # message_to_clu remains user_message
        else:
            print("Message is in English or detection assumed English; sending as is to CLU.")

        clu_response_data = call_clu_api(message_to_clu)
        print(f"CLU response data: {json.dumps(clu_response_data)}")
        bot_response_text = generate_bot_response(clu_response_data) 
        print(f"Bot response (English): {bot_response_text}")

        final_bot_response = bot_response_text
        # Translate back only if the original message was translated to English
        if translated_to_english and original_lang not in ['en', 'en-us']:
            try:
                print(f"Translating bot response from English to {original_lang}.")
                translator_to_original = GoogleTranslator(source='en', target=original_lang)
                final_bot_response = translator_to_original.translate(bot_response_text)
                print(f"Translated bot response to {original_lang}: {final_bot_response}")
            except (LanguageNotSupportedException, NotValidPayload, NotValidLength) as trans_e:
                print(f"Translation to {original_lang} failed: {str(trans_e)}. Sending English response.")
                # final_bot_response remains bot_response_text (English)
            except Exception as e:
                print(f"Unexpected error during translation to {original_lang}: {str(e)}. Sending English response.")
                # final_bot_response remains bot_response_text (English)
        
        return jsonify({"response": final_bot_response})

    except Exception as e:
        print(f"Error in /chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"response": "Sorry, a critical error occurred on my end. Please try again later."}), 500


if __name__ == "__main__":
    # Make sure menu.json exists before starting
    try:
        with open("menu.json", "r") as f:
            pass
        print("menu.json loaded successfully.")
    except FileNotFoundError:
        print("FATAL ERROR: menu.json not found. Please create this file before running.")
        exit(1)
    except json.JSONDecodeError:
        print("FATAL ERROR: menu.json is not valid JSON. Please fix the file before running.")
        exit(1)

    # Use host='0.0.0.0' to be accessible on the network
    # debug=False for production
    print("Starting Flask server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
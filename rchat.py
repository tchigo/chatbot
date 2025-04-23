from flask import Flask, render_template, request, jsonify
import requests
import json
import random

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
    print("Error: menu.json not found in the project directory.")
    MENU_DATA = {}

# Function to call Azure CLU API
def call_clu_api(user_input):
    headers = {
        "Ocp-Apim-Subscription-Key": CLU_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "kind": "Conversation",
        "analysisInput": {
            "conversationItem": {
                "id": "1",
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
        response = requests.post(CLU_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Function to generate bot response based on CLU output
def generate_bot_response(clu_response):
    if "error" in clu_response:
        return f"Error: {clu_response['error']}. Please try again later."

    result = clu_response.get("result", {})
    prediction = result.get("prediction", {})
    top_intent = prediction.get("topIntent", "None")
    intents = prediction.get("intents", [])
    entities = prediction.get("entities", [])

    # Extract entity values
    def get_entity(category):
        return next((e["text"] for e in entities if e["category"] == category), None)

    food_item = get_entity("Food_Items")
    quantity = get_entity("Quantity")
    order_details = get_entity("Order_Details")
    accompaniment = get_entity("Accompaniment")
    drink = get_entity("Drinks")
    address = get_entity("Address")
    food_category = get_entity("Food_Category")
    table = get_entity("Table")

    # Check for Feedback intent confidence
    feedback_intent = next((intent for intent in intents if intent.get("category") == "Feedback"), None)
    if feedback_intent and feedback_intent.get("confidence", 0) > 0.8:  # Use a higher threshold for Feedback
        return "Wow, thanks for the love! We’re thrilled you enjoyed your experience. What was your favorite part—food, vibe, or service? Share more, and we’ll keep the good times coming!"
    elif feedback_intent and feedback_intent.get("confidence", 0) > 0.5:
        return "Thanks for your feedback—we value it! Sorry if something didn’t hit the mark. Could you tell me more about your experience, like what dish or service issue, so we can make it right?"

    # Intent-based response logic
    if top_intent == "Greeting":
        greetings = [
            "Hey, welcome to our restaurant! Ready to explore our delicious menu or make a reservation?",
            "Hello there! Hungry for some gourmet burgers or maybe a pizza? How can I help you today?",
            "Hi, great to see you! What’s on your mind—food, drinks, or a table for tonight?"
        ]
        return random.choice(greetings)

    elif top_intent == "Order_Food":
        if food_item or food_category:
            response = "Awesome, let’s get your order started! You’ve chosen "
            if quantity:
                response += f"{quantity} "
            if food_item:
                response += f"{food_item}"
            elif food_category:
                response += f"{food_category.lower()}"
            if order_details:
                response += f" customized with {order_details}"
            if accompaniment:
                response += f" and {accompaniment} on the side"
            if drink:
                response += f", paired with a refreshing {drink}"
            response += ". Is this for dine-in, takeout, or delivery? Any other items you’d like to add?"
            return response
        return "Could you clarify what you’d like to order? For example, say '2 Spécial Chef Burgers with no mayo' or 'a Margherita Pizza with extra basil'."

    elif top_intent == "Menu_Inquiry":
        if food_category:
            category_key = next((key for key in MENU_DATA["categories"] if food_category.lower() in key.lower()), None)
            if category_key:
                items = ", ".join(MENU_DATA["categories"][category_key]["items"][:5])  # Limit to 5 items
                return f"Our {food_category.lower()} selection is top-notch! You can choose from {items}, and more. Want details on any of these or something specific, like ingredients or vegan options?"
            return f"Sorry, I couldn’t find {food_category} on our menu. Try asking about Gourmet Burgers, Tacos, Pizzas, or Desserts!"
        return "Our menu is packed with goodies! Think Gourmet Burgers like the Spécial Chef, Tacos with zesty fillings, Pizzas with tomato or cream bases, Kebab Sandwiches, Bowls, and decadent Desserts. Want to dive into a specific category or hear about our best-sellers?"

    elif top_intent == "Reservation":
        time = get_entity("Time") or "an unspecified time"
        people = quantity or "an unspecified number"
        if table:
            return f"Got it! Reserving a {table} table for {people} at {time}. Please confirm the date or let me know if it’s for today. Any special requests, like a window seat?"
        return f"Alright, booking a table for {people} at {time}. Could you specify the date or confirm if this is for today? Also, any preference for indoor or outdoor seating?"

    elif top_intent == "Cancellation":
        return "No worries, I can help cancel your order or reservation. Please share the order number or reservation details (like name and time) so I can confirm the cancellation for you."

    elif top_intent == "Pricing":
        if food_item:
            return f"The {food_item} is priced based on size and customizations. A standard {food_item} is around $8-$15. Want to add extras like {accompaniment or 'cheese'} or pair it with a {drink or 'Coca-Cola'}? Let me know for a precise quote!"
        return "Prices vary by item. For example, Gourmet Burgers start at $10, Tacos at $3 each, and Pizzas from $12. Could you specify an item, like 'How much is a Spécial Chef Burger?' for details?"

    elif top_intent == "Contact_Information":
        return "Reach us at (123) 456-7890, email info@restaurant.com, or visit us at 123 Flavor Street, Foodie Town. Want our social media handles or opening hours too?"

    elif top_intent == "Customer_Address":
        if address:
            return f"Thanks for sharing your address: {address}. Is this for a delivery order, or are you planning a visit? Let me know how I can assist further!"
        return "Please provide your address so I can help with delivery or other requests. For example, say '123 Main St, Foodie Town'."

    elif top_intent == "Hours_of_Operation":
        return "We’re open daily from 11 AM to 10 PM, ready to serve you burgers, tacos, and more! Planning to swing by soon or need help with something else?"

    elif top_intent == "Complaint":
        return "I’m really sorry to hear something went wrong. Could you share details, like a mix-up with your {food_item or 'order'} or a service issue? We’ll do our best to fix it and make your next visit awesome!"

    elif top_intent == "Hate_Speech_Offensive":
        return "Let’s keep the vibe positive! 😊 How about checking out our menu or asking for a recommendation instead? Our Spécial Chef Burger is a crowd-pleaser!"

    elif top_intent == "Recommendation":
        recommendations = [
            "You can’t go wrong with our Spécial Chef Gourmet Burger—loaded with premium ingredients and paired with Frites Maison!",
            "Try the Margherita Pizza with fresh basil and mozzarella for a classic Italian vibe.",
            "Our Tacos XL with Kebab filling and extra Harissa sauce are perfect for a spicy kick!",
            "Craving something sweet? The Tiramisu from our Desserts menu is a fan favorite."
        ]
        if food_category:
            category_key = next((key for key in MENU_DATA["categories"] if food_category.lower() in key.lower()), None)
            if category_key:
                item = random.choice(MENU_DATA["categories"][category_key]["items"])
                return f"For {food_category.lower()}, I recommend the {item}. It’s a hit with our regulars! Want to customize it with {accompaniment or 'extra cheese'} or pair it with a {drink or 'Coca-Cola'}?"
        return random.choice(recommendations) + " Want more suggestions or details on this one?"

    elif top_intent == "Extra_Service":
        return "Looking for something special? We offer catering for events, private dining rooms, or custom orders like birthday cakes. What’s the occasion, and how can we make it epic?"

    elif top_intent == "Order_Type":
        return "Good call! Are you dining in for the full restaurant experience, grabbing takeout, or having your order delivered to {address or 'your address'}? Let me know to get it set up!"

    else:
        return "Hmm, I didn’t quite catch that. Could you try something like 'Order a pizza', 'What’s on the menu?', or 'Book a table for 4'? I’m here to help!"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"response": "Please enter a message."})
    
    # Call CLU API and generate response
    clu_response = call_clu_api(user_message)
    bot_response = generate_bot_response(clu_response)
    return jsonify({"response": bot_response})

if __name__ == "__main__":
    app.run(debug=True)
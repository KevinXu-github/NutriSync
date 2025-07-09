# NutriSync

A food delivery email parser that automatically logs meals to MyFitnessPal.

## Current Status
- ✅ Basic Flask app setup
- ✅ Email parser framework
- ✅ DoorDash email parsing (working!)
- ✅ Mailgun webhook integration
- 🚧 Uber Eats email parsing (in progress)
- ⏳ MyFitnessPal integration (planned)
- ⏳ Nutrition API integration (planned)

## How It Works

1. **Forward emails**: User forwards DoorDash confirmation emails to their unique Mailgun address
2. **Parse orders**: App extracts restaurant, items, and prices from the email
3. **Get nutrition data**: Look up calories and macros for each food item
4. **Log to MyFitnessPal**: Automatically add the meal to user's food diary

## Current Parsing Results

Successfully parses DoorDash emails and extracts:
- ✅ Restaurant name
- ✅ Order total
- ✅ Individual items with quantities and prices
- ✅ All 4 items found correctly

## Setup

```bash
pip install flask beautifulsoup4
python app.py
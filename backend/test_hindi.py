import sys
import os
import json

# Add parent dir to path to import backend modules
sys.path.append(os.getcwd())

from intent_extractor import extract_intent

def test_hindi():
    sentences = [
        "मुझे बुखार है", # I have fever
        "मंगलुरु में त्वचा रोग विशेषज्ञ चाहिए", # Need skin specialist in Mangalore
        "बेंगलुरु में आँख के डॉक्टर चाहिए", # Need eye doctor in Bangalore
        "शिमोगा में दिल के डॉक्टर कहाँ हैं", # Where is heart specialist in Shimoga
    ]
    
    results = []
    for s in sentences:
        intent = extract_intent(s)
        results.append({
            "input": s,
            "intent": intent
        })
    
    with open('hindi_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results written to hindi_results.json")

if __name__ == '__main__':
    test_hindi()

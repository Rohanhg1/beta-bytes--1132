import sys
import os
import json

# Add parent dir to path to import backend modules
sys.path.append(os.getcwd())

from intent_extractor import extract_intent

def test_kannada():
    sentences = [
        "ನನಗೆ ಜ್ವರ ಬಂದಿದೆ", # I have fever
        "ಮಂಗಳೂರಿನಲ್ಲಿ ಚರ್ಮದ ಕಾಯಿಲೆಗೆ ವೈದ್ಯರ ಬೇಕು", # Need doctor for skin disease in Mangalore
        "ಬೆಂಗಳೂರಿನಲ್ಲಿ ಕಣ್ಣಿನ ವೈದ್ಯರು ಬೇಕು", # Need eye doctor in Bangalore
        "ಶಿವಮೊಗ್ಗದಲ್ಲಿ ಹಾರ್ಟ್ ಸ್ಪೆಷಲಿಸ್ಟ್ ಎಲ್ಲಿದ್ದಾರೆ", # Where is heart specialist in Shivamogga
    ]
    
    results = []
    for s in sentences:
        intent = extract_intent(s)
        results.append({
            "input": s,
            "intent": intent
        })
    
    with open('kannada_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Results written to kannada_results.json")

if __name__ == '__main__':
    test_kannada()

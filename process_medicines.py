import csv
import json
import os
import re

def clean_html(text):
    if not text:
        return ""
    # Remove HTML tags if any (though sample looked like plain text with some caps)
    clean = re.sub('<.*?>', '', text)
    return clean.strip()

def process_csv(input_path, output_path):
    print(f"Processing {input_path}...")
    medicines = []
    
    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Limit to a reasonable number of entries for RAG performance if it's too huge
            # but 24,000 rows (as seen in view_file) is manageable.
            
            # Extract basic info
            med_id = f"MED-{i+1:05d}"
            med_name = row.get('med_name', 'Unknown Medicine')
            generic = row.get('generic_name', 'N/A')
            content = clean_html(row.get('drug_content', ''))
            
            # Create a structured title
            title = f"{med_name}"
            if generic and generic != 'N/A':
                title += f" ({generic})"
            
            # Key recommendations can include variant and prescription status
            recommendations = []
            variant = row.get('drug_varient', '')
            if variant:
                recommendations.append(f"Variant: {variant.strip('* ')}")
            
            rx = row.get('prescription_required', '')
            if rx:
                recommendations.append(f"Prescription: {rx}")
                
            entry = {
                "id": med_id,
                "domain": "Pharmacology",
                "title": title,
                "source": "Medicines Dataset (Kaggle)",
                "category": "Drug Information",
                "content": content,
                "key_recommendations": recommendations,
                "last_updated": "2024-04-14" # Current processing date
            }
            medicines.append(entry)
            
            if (i + 1) % 5000 == 0:
                print(f"Processed {i + 1} rows...")

    print(f"Writing {len(medicines)} entries to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"guidelines": medicines}, f, indent=2)
    print("Processing complete.")

if __name__ == "__main__":
    input_csv = "data/medicines.csv"
    output_json = "data/medicines_data.json"
    
    if os.path.exists(input_csv):
        process_csv(input_csv, output_json)
    else:
        print(f"Error: {input_csv} not found.")

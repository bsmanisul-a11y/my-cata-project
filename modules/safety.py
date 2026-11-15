"""
Clinical Safety & Drug Interaction Engine for Elderly Care Platform
Provides real-time analysis of active medications to prevent adverse drug events,
food/supplement interactions, and high-risk elderly medication issues (Beers Criteria).
"""

INTERACTION_RULES = [
    {
        "drugs": ["warfarin", "aspirin"],
        "severity": "danger",
        "title": "Severe Bleeding Risk",
        "description": "Combining Warfarin (blood thinner) and Aspirin exponentially increases the risk of serious gastrointestinal and internal bleeding.",
        "action": "Consult your cardiologist or physician immediately to ensure co-administration is strictly intended and monitored."
    },
    {
        "drugs": ["warfarin", "ibuprofen"],
        "severity": "danger",
        "title": "Severe Bleeding & Stomach Ulcer Risk",
        "description": "NSAIDs like Ibuprofen dramatically amplify Warfarin's anticoagulant effects and irritate gastric lining.",
        "action": "Avoid Ibuprofen. Acetaminophen/Paracetamol is generally preferred for mild pain, under physician guidance."
    },
    {
        "drugs": ["lisinopril", "potassium"],
        "severity": "warning",
        "title": "Hyperkalemia (High Potassium) Risk",
        "description": "Lisinopril (ACE inhibitor) reduces potassium excretion. Taking potassium supplements or salt substitutes can elevate potassium to dangerous levels causing cardiac arrhythmias.",
        "action": "Do not take potassium supplements without regular blood monitoring by your doctor."
    },
    {
        "drugs": ["atorvastatin", "grapefruit"],
        "severity": "warning",
        "title": "Food Interaction: Grapefruit with Statins",
        "description": "Grapefruit inhibits the CYP3A4 enzyme that metabolizes Atorvastatin/Simvastatin, drastically raising medicine levels in the bloodstream and risking severe muscle damage.",
        "action": "Avoid grapefruit juice or whole grapefruit while taking statin medications."
    },
    {
        "drugs": ["metformin", "alcohol"],
        "severity": "warning",
        "title": "Metformin & Lactic Acidosis Caution",
        "description": "Alcohol intake while on Metformin significantly increases the risk of hypoglycemia and potentially life-threatening lactic acidosis.",
        "action": "Limit or avoid alcohol consumption. Ensure meals are not skipped."
    },
    {
        "drugs": ["levothyroxine", "calcium"],
        "severity": "info",
        "title": "Absorption Interference",
        "description": "Calcium supplements bond to Levothyroxine in the stomach, preventing your body from absorbing the thyroid hormone.",
        "action": "Take Levothyroxine on an empty stomach in the morning, and wait at least 4 hours before taking calcium supplements."
    },
    {
        "drugs": ["levothyroxine", "iron"],
        "severity": "info",
        "title": "Iron Interferes with Thyroid Hormone",
        "description": "Iron supplements significantly decrease the absorption of Levothyroxine.",
        "action": "Space your iron supplement at least 4 hours apart from your thyroid dose."
    },
    {
        "drugs": ["metoprolol", "ibuprofen"],
        "severity": "warning",
        "title": "Reduced Blood Pressure Efficacy",
        "description": "Regular use of NSAIDs like Ibuprofen can diminish the blood-pressure lowering effects of Metoprolol and cause fluid retention.",
        "action": "Discuss alternative pain management with your doctor if you require frequent pain relief."
    },
    {
        "drugs": ["clopidogrel", "omeprazole"],
        "severity": "warning",
        "title": "Reduced Antiplatelet Activation",
        "description": "Omeprazole inhibits the metabolic conversion of Clopidogrel (Plavix) to its active form, reducing its heart protection benefits.",
        "action": "Consult your physician regarding alternative acid-reducers such as Pantoprazole or Famotidine."
    }
]

FOOD_AND_TIMING_TIPS = {
    "metformin": "Take with meals (e.g. dinner or breakfast) to reduce common stomach upset.",
    "lisinopril": "Can be taken with or without food. Take at roughly the same time each morning.",
    "atorvastatin": "Can be taken anytime, but evening is often recommended. Avoid grapefruit.",
    "levothyroxine": "Strictly take on an empty stomach with a full glass of water, 30-60 mins before breakfast.",
    "amlodipine": "Take at the same time each day, with or without food. Monitor for ankle swelling.",
    "omeprazole": "Take 30 to 60 minutes before your first meal of the day.",
    "furosemide": "Take in the morning to prevent frequent nighttime urination disrupting your sleep.",
    "aspirin": "Always take with food or milk to safeguard stomach lining.",
    "alendronate": "Take first thing in the morning with plain water. Stay upright (sitting/standing) for 30 mins."
}

def check_drug_interactions(medication_list):
    """
    Given a list of medication names (e.g. ['Lisinopril 10mg', 'Warfarin 2.5mg', 'Aspirin 81mg']),
    returns detected interactions with severity level and recommendation.
    """
    normalized_names = [m.lower() for m in medication_list]
    detected_alerts = []
    
    for rule in INTERACTION_RULES:
        req_drugs = rule["drugs"]
        matches = [d for d in req_drugs if any(d in name for name in normalized_names)]
        if len(matches) == len(req_drugs):
            detected_alerts.append({
                "severity": rule["severity"],
                "title": rule["title"],
                "matched": matches,
                "description": rule["description"],
                "action": rule["action"]
            })
            
    # Check for duplicate therapeutic classes (e.g., multiple BP meds or multiple NSAIDs)
    bp_keywords = ["lisinopril", "amlodipine", "losartan", "metoprolol", "atenolol", "hydrochlorothiazide"]
    bp_count = sum(1 for kw in bp_keywords if any(kw in name for name in normalized_names))
    if bp_count >= 3:
        detected_alerts.append({
            "severity": "info",
            "title": "Multiple Antihypertensive Medications",
            "matched": ["blood pressure combination"],
            "description": f"You are currently taking {bp_count} blood pressure regulating medications.",
            "action": "Rise slowly from sitting or lying down to prevent dizziness or postural orthostatic hypotension."
        })
        
    return detected_alerts

def get_medication_advice(med_name):
    """Returns senior-friendly food & administration advice for a medication."""
    med_lower = med_name.lower()
    for drug_key, advice in FOOD_AND_TIMING_TIPS.items():
        if drug_key in med_lower:
            return advice
    return "Take consistently with water as prescribed by your doctor. Contact your pharmacist with questions."

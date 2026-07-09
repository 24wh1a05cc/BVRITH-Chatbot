"""
BVRITH Image Gallery Module
Maps user queries about photos/images to real BVRITH college images.
Images are loaded from the official BVRITH website (bvrithyderabad.edu.in).
"""

from typing import List, Dict, Any
import re

# ============================================================
# IMAGE CATEGORIES & MAPPING
# ============================================================

# Real images from BVRITH official website
IMAGE_CATEGORIES = {
    "campus": {
        "title": "🏛️ Campus Views",
        "keywords": ["campus", "college", "building", "infrastructure", "view", "aerial", "ground"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/home-slider-6-bvrit-hyderabad-engineering-women-college-1024x435.webp",
                "caption": "BVRITH College Campus Overview",
                "alt": "BVRIT Hyderabad Engineering Women College Campus"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/home-section-img2-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "BVRITH College Building",
                "alt": "BVRIT Hyderabad College Building"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/WelcomeBVRITH.jpg",
                "caption": "Welcome to BVRITH - College Entrance",
                "alt": "Welcome to BVRITH"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/ApjIngate.jpg",
                "caption": "APJ Abdul Kalam Gate at BVRITH",
                "alt": "APJ Abdul Kalam Gate"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/CSE-SITA-BLOCK1.jpg",
                "caption": "CSE & SITA Block at BVRITH",
                "alt": "CSE SITA Block"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/MemorialHall1.jpg",
                "caption": "Memorial Hall at BVRITH",
                "alt": "Memorial Hall"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/VSCC2.jpg",
                "caption": "Vishnu Sri Chaitanya Centre (VSCC)",
                "alt": "VSCC Building"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/01/SMB1.jpg",
                "caption": "SMB Block at BVRITH",
                "alt": "SMB Block"
            },
        ]
    },
    "events": {
        "title": "🎉 Events & Celebrations",
        "keywords": ["event", "celebration", "fest", "synergia", "annual", "day", "function", "cultural", "technical"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/Synergia-26.jpg",
                "caption": "Synergia 2026 - Technical & Cultural Fest",
                "alt": "Synergia 2026"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/annualday1.jpg",
                "caption": "Annual Day Celebration at BVRITH",
                "alt": "Annual Day Celebration"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics0.jpg",
                "caption": "Annual Day - Cultural Performance",
                "alt": "Annual Day Performance"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics1.jpg",
                "caption": "Annual Day - Student Performances",
                "alt": "Annual Day Students"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics2.jpg",
                "caption": "Annual Day - Dance Performance",
                "alt": "Annual Day Dance"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics3.jpg",
                "caption": "Annual Day - Group Performance",
                "alt": "Annual Day Group"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics4.jpg",
                "caption": "Annual Day - Award Ceremony",
                "alt": "Annual Day Awards"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics5.jpg",
                "caption": "Annual Day - Chief Guest Address",
                "alt": "Annual Day Chief Guest"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics6.jpg",
                "caption": "Annual Day - Cultural Event",
                "alt": "Annual Day Cultural"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics7.jpg",
                "caption": "Annual Day - Student Gathering",
                "alt": "Annual Day Gathering"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics8.jpg",
                "caption": "Annual Day - Lighting Ceremony",
                "alt": "Annual Day Lighting"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics9.jpg",
                "caption": "Annual Day - Musical Performance",
                "alt": "Annual Day Music"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics10.jpg",
                "caption": "Annual Day - Group Photo",
                "alt": "Annual Day Group Photo"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics11.jpg",
                "caption": "Annual Day - Decoration",
                "alt": "Annual Day Decoration"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics12.jpg",
                "caption": "Annual Day - Audience",
                "alt": "Annual Day Audience"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics13.jpg",
                "caption": "Annual Day - Stage Performance",
                "alt": "Annual Day Stage"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics14.jpg",
                "caption": "Annual Day - Felicitation",
                "alt": "Annual Day Felicitation"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics15.jpg",
                "caption": "Annual Day - Cultural Show",
                "alt": "Annual Day Show"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics16.jpg",
                "caption": "Annual Day - Student Activities",
                "alt": "Annual Day Activities"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics17.jpg",
                "caption": "Annual Day - Closing Ceremony",
                "alt": "Annual Day Closing"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/04/AnnualDayPics18.jpg",
                "caption": "Annual Day - Grand Finale",
                "alt": "Annual Day Finale"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/03/Milan2026.jpg",
                "caption": "Milan 2026 - Cultural Event",
                "alt": "Milan 2026"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/02/TedX.jpg",
                "caption": "TEDx Event at BVRITH",
                "alt": "TEDx BVRITH"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/03/Synergia2026-banner.jpeg",
                "caption": "Synergia 2026 Banner",
                "alt": "Synergia 2026 Banner"
            },
        ]
    },
    "placements": {
        "title": "💼 Placements & Recruiters",
        "keywords": ["placement", "recruiter", "company", "job", "career", "offer", "selected", "placed"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2026/02/GooglePlacements.jpeg",
                "caption": "Google Placements at BVRITH",
                "alt": "Google Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/Adobe-FTE-Select-2022-26-1.jpg",
                "caption": "Adobe FTE Selections at BVRITH",
                "alt": "Adobe Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/amazon-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Amazon Placements at BVRITH",
                "alt": "Amazon Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/microsoft-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Microsoft Placements at BVRITH",
                "alt": "Microsoft Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/infosys-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Infosys Placements at BVRITH",
                "alt": "Infosys Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/accenture-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Accenture Placements at BVRITH",
                "alt": "Accenture Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/flipkart-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Flipkart Placements at BVRITH",
                "alt": "Flipkart Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/athena-health-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Athena Health Placements at BVRITH",
                "alt": "Athena Health Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/04/providence-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Providence Placements at BVRITH",
                "alt": "Providence Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/virtusa-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Virtusa Placements at BVRITH",
                "alt": "Virtusa Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/vmware-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "VMware Placements at BVRITH",
                "alt": "VMware Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/goldmasachs-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Goldman Sachs Placements at BVRITH",
                "alt": "Goldman Sachs Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/jp-morgan-chase-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "JP Morgan Chase Placements at BVRITH",
                "alt": "JP Morgan Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/DBS-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "DBS Placements at BVRITH",
                "alt": "DBS Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/cognizan-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Cognizant Placements at BVRITH",
                "alt": "Cognizant Placements"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/06/adobe-placement-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Adobe Placements at BVRITH",
                "alt": "Adobe Placements"
            },
        ]
    },
    "leadership": {
        "title": "👨‍🏫 Leadership & Faculty",
        "keywords": ["chairman", "director", "principal", "faculty", "teacher", "leadership", "management", "vice chairman", "secretary"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/09/Chairman-Sir.jpg",
                "caption": "Chairman Sri K.V. Vishnu Raju",
                "alt": "Chairman BVRITH"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/09/VC-Sir.jpg",
                "caption": "Vice Chairman Sri Ravichandran Rajagopal",
                "alt": "Vice Chairman BVRITH"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/09/DirectorSir.jpg",
                "caption": "Director of BVRITH",
                "alt": "Director BVRITH"
            },
        ]
    },
    "students": {
        "title": "👩‍🎓 Student Life",
        "keywords": ["student", "classroom", "lab", "library", "study", "learning", "girls", "women", "hostel"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2023/05/yoga-7-bvrith-image-bvrit-hyderabad-engineering-women-college.webp",
                "caption": "Yoga Day Celebration at BVRITH",
                "alt": "Yoga at BVRITH"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/Gold-Medal.jpg",
                "caption": "Gold Medal Winners at BVRITH",
                "alt": "Gold Medal Winners"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/Gold-Medal-2.jpg",
                "caption": "Gold Medal Ceremony at BVRITH",
                "alt": "Gold Medal Ceremony"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/12/SIH-2025-winners-1.jpg",
                "caption": "SIH 2025 Winners from BVRITH",
                "alt": "SIH 2025 Winners"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/12/SIH-ECE.jpg",
                "caption": "SIH 2025 - ECE Team from BVRITH",
                "alt": "SIH ECE Team"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/bsfi.jpg",
                "caption": "BSFI Event at BVRITH",
                "alt": "BSFI Event"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/Graduation-Day-2025.jpg",
                "caption": "Graduation Day 2025 at BVRITH",
                "alt": "Graduation Day 2025"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/SVES-USA-Alumni-Meet.jpg",
                "caption": "SVES USA Alumni Meet",
                "alt": "SVES Alumni Meet"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/11/Penn-State-College-of-Engg.jpg",
                "caption": "Penn State Collaboration at BVRITH",
                "alt": "Penn State Collaboration"
            },
        ]
    },
    "awards": {
        "title": "🏆 Awards & Recognition",
        "keywords": ["award", "recognition", "achievement", "nirf", "naac", "nba", "accreditation", "rank"],
        "images": [
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/06/csiAward.jpg",
                "caption": "CSI Award Received by BVRITH",
                "alt": "CSI Award"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2025/06/PMVidyaLaxmi.jpg",
                "caption": "PM Vidya Laxmi Initiative at BVRITH",
                "alt": "PM Vidya Laxmi"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2021/09/Principal-Award-copy.jpg",
                "caption": "Principal's Award at BVRITH",
                "alt": "Principal Award"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2021/09/AICTEs-360-Degree-Feedback-Portal-AWD10010.jpg",
                "caption": "AICTE 360 Degree Feedback Award",
                "alt": "AICTE Award"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2024/03/Dr-J-Naga-Vishnu-Vardhan-Mr-Priyakanth-Mr-Sai-Kumar-Tara-for-receiving-Best-faculty-Awards-from-AIMERS.jpeg",
                "caption": "Best Faculty Awards from AIMERS",
                "alt": "Best Faculty Awards"
            },
            {
                "url": "https://bvrithyderabad.edu.in/wp-content/uploads/2024/03/Life-Time-Achievment-Award-AIMERS.jpeg",
                "caption": "Lifetime Achievement Award from AIMERS",
                "alt": "Lifetime Achievement Award"
            },
        ]
    },
    "general": {
        "title": "📸 BVRITH Photo Gallery",
        "keywords": ["photo", "image", "picture", "gallery", "photos", "images", "pictures", "show", "view"],
        "images": []  # Will be populated with a mix of all images
    }
}

# Build the "general" category as a mix of all images
_all_images = []
for cat_key, cat_data in IMAGE_CATEGORIES.items():
    if cat_key != "general":
        _all_images.extend(cat_data["images"])
IMAGE_CATEGORIES["general"]["images"] = _all_images


def is_image_query(query: str) -> bool:
    """
    Detect if a user query is asking for images/photos.
    
    Returns True if the query contains image-related keywords.
    """
    image_keywords = [
        "photo", "photos", "image", "images", "picture", "pictures",
        "gallery", "show me", "show", "view", "campus photo",
        "college photo", "look like", "visual", "see",
        "snap", "snapshot", "photograph", "photographs",
        "pic", "pics",
    ]
    
    query_lower = query.lower().strip()
    
    # Check for direct image requests
    for kw in image_keywords:
        if kw in query_lower:
            return True
    
    # Check for "photo of X" or "image of X" patterns
    photo_patterns = [
        r'\b(photo|image|picture|pic)\s+of\b',
        r'\b(photos|images|pictures|pics)\s+of\b',
        r'\bshow\s+(me\s+)?(photo|image|picture|pic|photos|images|pictures|pics)\b',
        r'\b(how\s+does|what\s+does)\s+.*\b(look\s+like)\b',
    ]
    
    for pattern in photo_patterns:
        if re.search(pattern, query_lower):
            return True
    
    return False


def get_category_for_query(query: str) -> str:
    """
    Determine which image category best matches the query.
    
    Returns the category key (e.g., "campus", "events", "placements", etc.)
    """
    query_lower = query.lower().strip()
    
    # Check each category's keywords
    best_category = "general"
    best_match_count = 0
    
    for cat_key, cat_data in IMAGE_CATEGORIES.items():
        if cat_key == "general":
            continue
        match_count = sum(1 for kw in cat_data["keywords"] if kw in query_lower)
        if match_count > best_match_count:
            best_match_count = match_count
            best_category = cat_key
    
    return best_category


def get_images_for_query(query: str, max_images: int = 12) -> Dict[str, Any]:
    """
    Get images matching a user query.
    
    Args:
        query: The user's question/query
        max_images: Maximum number of images to return
    
    Returns:
        Dict with category info and list of image dicts
    """
    category = get_category_for_query(query)
    cat_data = IMAGE_CATEGORIES[category]
    images = cat_data["images"][:max_images]
    
    return {
        "category": category,
        "title": cat_data["title"],
        "images": images,
        "total": len(cat_data["images"]),
        "showing": len(images),
    }


def get_all_categories() -> List[Dict[str, Any]]:
    """Get all image categories with their metadata."""
    categories = []
    for cat_key, cat_data in IMAGE_CATEGORIES.items():
        categories.append({
            "key": cat_key,
            "title": cat_data["title"],
            "count": len(cat_data["images"]),
        })
    return categories
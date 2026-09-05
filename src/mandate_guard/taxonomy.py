"""Original hierarchical product taxonomy for category-semantic T1 features."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
from sklearn.metrics.pairwise import cosine_similarity  # type: ignore[import-untyped]

TAXONOMY_LEAVES: list[str] = [
    "Electronics > Computer Accessories > Wireless Mouse",
    "Electronics > Computer Accessories > USB-C Hub",
    "Electronics > Computer Accessories > Webcam",
    "Electronics > Computer Accessories > Mechanical Keyboard",
    "Electronics > Computer Accessories > Laptop Stand",
    "Electronics > Audio > Bluetooth Speaker",
    "Electronics > Audio > Wireless Earbuds",
    "Electronics > Audio > Speaker",
    "Electronics > Audio > Headphones",
    "Electronics > Mobile > Phone Charger",
    "Electronics > Mobile > Power Bank",
    "Electronics > Mobile > Tablet Stylus",
    "Electronics > Displays > Monitor Arm",
    "Electronics > Displays > Monitor",
    "Electronics > Cables > HDMI Cable",
    "Electronics > Storage > SD Card Reader",
    "Electronics > Storage > USB Flash Drive",
    "Electronics > Office > Desk Lamp",
    "Groceries > Pantry > Organic Pasta",
    "Groceries > Pantry > Rice Noodles",
    "Groceries > Pantry > Olive Oil",
    "Groceries > Pantry > Brown Rice",
    "Groceries > Pantry > Honey Jar",
    "Groceries > Snacks > Granola Bars",
    "Groceries > Snacks > Trail Mix",
    "Groceries > Snacks > Dried Fruit Mix",
    "Groceries > Beverages > Coffee Beans",
    "Groceries > Beverages > Herbal Tea",
    "Groceries > Beverages > Green Tea",
    "Groceries > Beverages > Sparkling Water",
    "Groceries > Beverages > Oat Milk",
    "Groceries > Spreads > Almond Butter",
    "Groceries > Spreads > Peanut Butter",
    "Home Goods > Organization > Storage Bin",
    "Home Goods > Organization > Closet Organizer",
    "Home Goods > Organization > Drawer Divider",
    "Home Goods > Kitchen > Cutting Board",
    "Home Goods > Kitchen > Dish Rack",
    "Home Goods > Kitchen > Food Storage Container",
    "Home Goods > Bedding > Bed Sheets",
    "Home Goods > Bedding > Pillow",
    "Home Goods > Bedding > Comforter",
    "Home Goods > Decor > Wall Clock",
    "Home Goods > Decor > Throw Blanket",
    "Home Goods > Decor > Area Rug",
    "Home Goods > Bath > Bath Towel",
    "Home Goods > Bath > Shower Curtain",
    "Apparel > Outerwear > Jacket",
    "Apparel > Outerwear > Raincoat",
    "Apparel > Footwear > Sneakers",
    "Apparel > Footwear > Sandals",
    "Apparel > Footwear > Boots",
    "Apparel > Tops > T-Shirt",
    "Apparel > Tops > Sweater",
    "Apparel > Bottoms > Jeans",
    "Apparel > Bottoms > Shorts",
    "Apparel > Accessories > Belt",
    "Apparel > Accessories > Scarf",
    "Apparel > Sleepwear > Pajama Set",
    "Health & Personal Care > Oral Care > Toothbrush",
    "Health & Personal Care > Oral Care > Toothpaste",
    "Health & Personal Care > Skin Care > Moisturizer",
    "Health & Personal Care > Skin Care > Sunscreen",
    "Health & Personal Care > Hair Care > Shampoo",
    "Health & Personal Care > Hair Care > Conditioner",
    "Health & Personal Care > Vitamins > Multivitamin",
    "Health & Personal Care > Vitamins > Fish Oil Capsules",
    "Health & Personal Care > First Aid > Adhesive Bandages",
    "Health & Personal Care > First Aid > Antiseptic Wipes",
    "Health & Personal Care > Personal Hygiene > Hand Sanitizer",
    "Health & Personal Care > Personal Hygiene > Deodorant",
    "Office Supplies > Writing > Ballpoint Pen",
    "Office Supplies > Writing > Mechanical Pencil",
    "Office Supplies > Paper > Notebook",
    "Office Supplies > Paper > Sticky Notes",
    "Office Supplies > Filing > Manila Folder",
    "Office Supplies > Filing > Binder Clips",
    "Office Supplies > Desk Accessories > Stapler",
    "Office Supplies > Desk Accessories > Tape Dispenser",
    "Office Supplies > Printing > Printer Paper",
    "Office Supplies > Printing > Ink Cartridge",
    "Office Supplies > Storage > File Box",
    "Office Supplies > Storage > Desk Organizer",
    "Toys & Games > Building Sets > Building Blocks",
    "Toys & Games > Building Sets > Model Kit",
    "Toys & Games > Board Games > Strategy Board Game",
    "Toys & Games > Board Games > Card Game",
    "Toys & Games > Puzzles > Jigsaw Puzzle",
    "Toys & Games > Puzzles > Brain Teaser",
    "Toys & Games > Outdoor Play > Frisbee",
    "Toys & Games > Outdoor Play > Jump Rope",
    "Toys & Games > Action Figures > Action Figure Set",
    "Toys & Games > Plush > Stuffed Animal",
    "Toys & Games > Educational > Flash Cards",
    "Toys & Games > Educational > Learning Tablet Toy",
    "Pet Supplies > Food > Dry Dog Food",
    "Pet Supplies > Food > Wet Cat Food",
    "Pet Supplies > Toys > Chew Toy",
    "Pet Supplies > Toys > Cat Wand Toy",
    "Pet Supplies > Grooming > Pet Shampoo",
    "Pet Supplies > Grooming > Pet Brush",
    "Pet Supplies > Habitat > Pet Bed",
    "Pet Supplies > Habitat > Litter Box",
    "Pet Supplies > Leashes & Collars > Dog Leash",
    "Pet Supplies > Leashes & Collars > Dog Collar",
    "Pet Supplies > Health > Flea Treatment",
    "Pet Supplies > Health > Pet Vitamins",
    "Automotive > Interior Accessories > Car Phone Mount",
    "Automotive > Interior Accessories > Seat Cover",
    "Automotive > Exterior Accessories > Car Cover",
    "Automotive > Exterior Accessories > Floor Mats",
    "Automotive > Maintenance > Motor Oil",
    "Automotive > Maintenance > Windshield Wiper Blades",
    "Automotive > Electronics > Dash Cam",
    "Automotive > Electronics > Car Charger",
    "Automotive > Cleaning > Car Wash Soap",
    "Automotive > Cleaning > Microfiber Cloth",
    "Automotive > Tools > Tire Pressure Gauge",
    "Automotive > Tools > Jump Starter",
    "Books & Media > Books > Paperback Novel",
    "Books & Media > Books > Hardcover Nonfiction Book",
    "Books & Media > Books > Cookbook",
    "Books & Media > Magazines > Monthly Magazine Subscription",
    "Books & Media > Music > Vinyl Record",
    "Books & Media > Music > CD Album",
    "Books & Media > Movies > Blu-ray Movie",
    "Books & Media > Movies > DVD Box Set",
    "Books & Media > Stationery Media > Journal Notebook",
    "Books & Media > Educational > Textbook",
]


def build_taxonomy_vectorizer() -> TfidfVectorizer:
    vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 1))
    vec.fit([leaf.replace(">", " ").lower() for leaf in TAXONOMY_LEAVES])
    return vec


def taxonomy_leaf_matrix(vec: TfidfVectorizer) -> Any:
    return vec.transform([leaf.replace(">", " ").lower() for leaf in TAXONOMY_LEAVES])


def best_matching_leaf_index(
    text: str,
    vec: TfidfVectorizer,
    leaf_matrix: Any,
) -> int:
    if not text.strip():
        return 0
    query = vec.transform([text.lower()])
    scores = cosine_similarity(query, leaf_matrix)[0]
    return int(scores.argmax())


def hierarchy_distance(leaf_index_a: int, leaf_index_b: int) -> float:
    path_a = TAXONOMY_LEAVES[leaf_index_a].split(" > ")
    path_b = TAXONOMY_LEAVES[leaf_index_b].split(" > ")
    shared = 0
    for segment_a, segment_b in zip(path_a, path_b, strict=False):
        if segment_a == segment_b:
            shared += 1
        else:
            break
    max_depth = max(len(path_a), len(path_b))
    if max_depth == 0:
        return 1.0
    return 1.0 - (shared / max_depth)

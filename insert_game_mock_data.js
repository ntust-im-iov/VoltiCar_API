// --- Connect to the correct database ---
// use Volticar;

// --- Insert Sample Shop Items ---
db.shop_items.insertMany([
  {
    "item_id": "tire_repair_kit",
    "name": "Tire Repair Kit",
    "description": "A kit to quickly repair a flat tire during a delivery.",
    "price": 150,
    "category": "consumable",
    "icon_url": "https://example.com/icons/tire_kit.png"
  },
  {
    "item_id": "coffee_boost",
    "name": "Coffee Boost",
    "description": "Reduces the time penalty from a 'fatigue' event.",
    "price": 50,
    "category": "consumable",
    "icon_url": "https://example.com/icons/coffee.png"
  },
  {
    "item_id": "gps_scrambler",
    "name": "GPS Scrambler",
    "description": "Avoid a random 'police check' event.",
    "price": 300,
    "category": "consumable",
    "icon_url": "https://example.com/icons/gps_scrambler.png"
  }
]);

// --- Insert Sample Charging Stations with Geo data ---
db.stations.insertMany([
    {
        "station_id": "station_A",
        "name": "Taipei 101 Supercharger",
        "latitude": 25.033961,
        "longitude": 121.564468,
        "city": "Taipei"
    },
    {
        "station_id": "station_B",
        "name": "Kaohsiung Art Center Charger",
        "latitude": 22.6319,
        "longitude": 120.3016,
        "city": "Kaohsiung"
    }
]);

print("Mock game data for shop items and stations inserted successfully.");

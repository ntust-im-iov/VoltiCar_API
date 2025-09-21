// This script connects to the Volticar database and drops collections
// to ensure a clean state for testing with the new UUID schema.

const dbName = 'Volticar';
const collectionsToDrop = [
    'Users',
    'Player',
    'PlayerVehicles',
    'PlayerAchievements',
    'PlayerTasks',
    'PlayerWarehouseItems',
    'GameSessions',
    'PendingVerifications',
    'OTPRecords',
    'LoginRecords'
];

const db = db.getSiblingDB(dbName);

print(`Targeting database: ${dbName}`);

collectionsToDrop.forEach(collName => {
    let collection = db.getCollection(collName);
    if (collection.exists()) {
        collection.drop();
        print(`Dropped collection: ${collName}`);
    } else {
        print(`Collection ${collName} does not exist, skipping.`);
    }
});

print("Cleanup script finished.");

// MongoDB Migration Script for ID Conversion to UUID
// ==================================================
// IMPORTANT:
// 1. BACKUP YOUR ENTIRE DATABASE BEFORE RUNNING THIS SCRIPT.
//    Example backup command (run in mongo shell or mongodump):
//    mongodump --uri="mongodb://YourUser:YourPassword@YourHost:YourPort/Volticar" --out="/path/to/backup_directory_YYYYMMDD"
// 2. RUN THIS SCRIPT IN A TEST ENVIRONMENT FIRST.
// 3. This script assumes it's being run directly against the 'Volticar' database.
//    If not, use 'use Volticar;' command first in the mongo shell before loading this script.
// 4. Ensure you have the necessary permissions to perform these operations.

print("Starting MongoDB ID Migration Script...");
print("=======================================");
print("STEP 0: ENSURE YOU HAVE BACKED UP YOUR DATABASE!");
print("Press Ctrl+C now if you haven't backed up.");
// Add a small delay or a confirmation step if possible in a real scenario,
// but for a script, this print is a reminder.

// --- Helper function to generate UUIDs if not available (MongoDB 4.0+ has UUID()) ---
// For older versions, you might need to ensure UUID() is available or use a different method.
if (typeof UUID === 'undefined') {
    print("Warning: UUID() function is not available. Trying to load a polyfill (for older MongoDB versions).");
    // Basic UUID v4 generator (RFC4122) - for environments where UUID() might not be standard
    UUID = function() {
        var d = new Date().getTime();
        if (typeof performance !== 'undefined' && typeof performance.now === 'function'){
            d += performance.now(); //use high-precision timer if available
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = (d + Math.random() * 16) % 16 | 0;
            d = Math.floor(d / 16);
            return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    };
    print("Basic UUID polyfill loaded. It's recommended to use MongoDB 4.0+ for native UUID().");
}


print("\nSTEP 1: Migrating 'Users' collection...");
// --------------------------------------------
try {
    // db.Users.aggregate([{ $match: {} }, { $out: "Users_backup_script_run" }]); // Optional: script-specific backup
    db.id_map_users.drop(); 
    db.createCollection("id_map_users");
    db.id_map_users.createIndex({ old_id: 1 }, { unique: true });
    db.id_map_users.createIndex({ new_id: 1 }); // new_id (original user_id) should also be unique

    print("Processing Users collection documents...");
    var bulkOps_users = []; 
    var processedCount_users = 0;
    var errorCount_users = 0;

    db.Users.find({}).forEach(function(doc) {
        var oldObjectId_users = doc._id;
        var newUuidId_users = doc.user_id; 

        if (!newUuidId_users || typeof newUuidId_users !== 'string' || newUuidId_users.length !== 36) { 
            print(`Users: ERROR - Doc with old _id ${oldObjectId_users} has invalid/missing user_id: ${newUuidId_users}. Skipping.`);
            errorCount_users++;
            return; 
        }
        try {
            db.id_map_users.insertOne({ old_id: oldObjectId_users, new_id: newUuidId_users });
        } catch (e) {
            print(`Users: ERROR - Inserting mapping for old_id ${oldObjectId_users} to new_id ${newUuidId_users}: ${e.message}. Skipping doc update.`);
            errorCount_users++;
            return; 
        }
        var newDoc_users = { ...doc }; 
        delete newDoc_users._id;       
        delete newDoc_users.user_id;   
        newDoc_users._id = newUuidId_users;  

        bulkOps_users.push({ deleteOne: { filter: { _id: oldObjectId_users } } });
        bulkOps_users.push({ insertOne: { document: newDoc_users } });
        processedCount_users++;
        if (bulkOps_users.length >= 1000) { // 500 docs = 1000 operations
            try { 
                var result = db.Users.bulkWrite(bulkOps_users, { ordered: false }); 
                print(`Users: Processed ${processedCount_users} (bulk exec). Matched: ${result.matchedCount}, Deleted: ${result.deletedCount}, Inserted: ${result.insertedCount}`);
            } catch (e) { print(`Users: Bulk write ERROR: ${e}`); }
            bulkOps_users = []; 
        }
    });
    if (bulkOps_users.length > 0) {
        try { 
            var result_final = db.Users.bulkWrite(bulkOps_users, { ordered: false }); 
            print(`Users: Processed final batch. Matched: ${result_final.matchedCount}, Deleted: ${result_final.deletedCount}, Inserted: ${result_final.insertedCount}`);
        } catch (e) { print(`Users: Final bulk write ERROR: ${e}`); }
    }
    print(`Users collection migration finished. Total documents processed for update: ${processedCount_users}. Errors encountered: ${errorCount_users}.`);
    print("Check 'id_map_users' collection for ID mappings.");
} catch (e) {
    print(`Users: CRITICAL ERROR during migration: ${e}`);
}

print("\nSTEP 2: Migrating 'LoginRecords' collection...");
// --------------------------------------------------
try {
    // db.LoginRecords.aggregate([{ $match: {} }, { $out: "LoginRecords_backup_script_run" }]);
    db.id_map_login_records.drop(); 
    db.createCollection("id_map_login_records");
    db.id_map_login_records.createIndex({ old_id: 1 }, { unique: true });
    db.id_map_login_records.createIndex({ new_id: 1 }, { unique: true });
    
    print("Processing LoginRecords collection documents...");
    var bulkOps_lr = [];
    var processedCount_lr = 0;
    var errorCount_lr = 0;
    var userMappingNotFoundCount_lr = 0;

    db.LoginRecords.find({}).forEach(function(lrDoc) {
        var oldLrId = lrDoc._id; 
        var newLrUuid = UUID().toString(); 

        try {
            db.id_map_login_records.insertOne({ old_id: oldLrId, new_id: newLrUuid });
        } catch (e) {
            print(`LoginRecords: ERROR - Inserting mapping for LR old_id ${oldLrId} to new_id ${newLrUuid}: ${e.message}. Skipping.`);
            errorCount_lr++; return;
        }
        var newUserIdRef_lr;
        if (lrDoc.user_id) {
            if (typeof lrDoc.user_id === 'string' && lrDoc.user_id.length === 36) { 
                newUserIdRef_lr = lrDoc.user_id; 
            } else { 
                var userMap_lr = db.id_map_users.findOne({ old_id: lrDoc.user_id });
                if (userMap_lr && userMap_lr.new_id) { 
                    newUserIdRef_lr = userMap_lr.new_id; 
                } else { 
                    print(`LoginRecords: WARNING - User mapping not found for user_id ${lrDoc.user_id} in LR ${oldLrId}. Skipping this document.`); 
                    userMappingNotFoundCount_lr++; 
                    try { db.id_map_login_records.deleteOne({ old_id: oldLrId }); } catch(del_err){ print(`LoginRecords: Error deleting temp mapping: ${del_err}`);}
                    errorCount_lr++; 
                    return; 
                }
            }
        } else { 
            print(`LoginRecords: WARNING - LR ${oldLrId} is missing user_id field. Skipping this document.`); 
            try { db.id_map_login_records.deleteOne({ old_id: oldLrId }); } catch(del_err){ print(`LoginRecords: Error deleting temp mapping: ${del_err}`);}
            errorCount_lr++; 
            return; 
        }
        
        var newLrDoc = { ...lrDoc };
        delete newLrDoc._id;
        newLrDoc._id = newLrUuid;       
        newLrDoc.user_id = newUserIdRef_lr; 

        bulkOps_lr.push({ deleteOne: { filter: { _id: oldLrId } } });
        bulkOps_lr.push({ insertOne: { document: newLrDoc } });
        processedCount_lr++;
        if (bulkOps_lr.length >= 1000) {
            try { 
                var result_lr = db.LoginRecords.bulkWrite(bulkOps_lr, { ordered: false }); 
                print(`LoginRecords: Processed ${processedCount_lr} (bulk exec). Matched: ${result_lr.matchedCount}, Deleted: ${result_lr.deletedCount}, Inserted: ${result_lr.insertedCount}`);
            } catch (e) { print(`LoginRecords: Bulk write ERROR: ${e}`); }
            bulkOps_lr = [];
        }
    });
    if (bulkOps_lr.length > 0) {
        try { 
            var result_lr_final = db.LoginRecords.bulkWrite(bulkOps_lr, { ordered: false }); 
            print(`LoginRecords: Processed final batch. Matched: ${result_lr_final.matchedCount}, Deleted: ${result_lr_final.deletedCount}, Inserted: ${result_lr_final.insertedCount}`);
        } catch (e) { print(`LoginRecords: Final bulk write ERROR: ${e}`); }
    }
    print(`LoginRecords collection migration finished. Total documents processed for update: ${processedCount_lr}. Errors: ${errorCount_lr}. User mappings not found: ${userMappingNotFoundCount_lr}.`);
    if (db.id_map_login_records.countDocuments() > 0) {
        print("Check 'id_map_login_records' for LoginRecord ID mappings (if needed for other references).");
    }
} catch (e) {
    print(`LoginRecords: CRITICAL ERROR during migration: ${e}`);
}

print("\nSTEP 3: Clearing other collections (containing mock data)...");
// -----------------------------------------------------------------
// IMPORTANT: Double-check this list before running!
var collectionsToClear = [
    "VehicleDefinitions",
    "ItemDefinitions",
    "TaskDefinitions",    // New name for 'Tasks'
    "Tasks",              // Old 'Tasks' collection, if it still exists and needs clearing
    "Destinations",
    "PlayerOwnedVehicles",// New name for player's vehicles
    "Vehicles",           // Old 'Vehicles' collection, if it still exists and needs clearing
    "PlayerWarehouseItems",
    "PlayerTasks",
    "GameSessions"
    // Add other collections confirmed for clearing:
    // "Achievements",
    // "Rewards",
    // "PendingVerifications",
    // "OTPRecords",
    // "Tokens" // Tokens are usually safe to clear
];

collectionsToClear.forEach(function(collName) {
    try {
        if (db.getCollectionNames().includes(collName)) {
            var deleteResult = db.getCollection(collName).deleteMany({});
            print(`Cleared collection '${collName}': ${deleteResult.deletedCount} documents deleted.`);
        } else {
            print(`Collection '${collName}' not found, skipping clearing.`);
        }
    } catch (e) {
        print(`Error clearing collection '${collName}': ${e}`);
    }
});
print("Finished clearing specified collections.");

print("\n=======================================");
print("MongoDB ID Migration Script COMPLETED.");
print("Review all output for errors or warnings.");
print("Verify data integrity and application functionality thoroughly.");

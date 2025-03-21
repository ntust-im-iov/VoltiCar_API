// 初始化Volticar数据库和用户集合
db = db.getSiblingDB('Volticar');

// 创建Users集合
if (!db.getCollectionNames().includes('Users')) {
    db.createCollection('Users');
    print('已创建Users集合');
}

// 创建charge_station数据库
db = db.getSiblingDB('charge_station');

// 预定义的城市列表
const cities = [
    'Taipei', 'NewTaipei', 'Taoyuan', 'Taichung', 'Tainan', 
    'Kaohsiung', 'Keelung', 'Hsinchu', 'ChiayiCounty', 
    'HsinchuCounty', 'MiaoliCounty', 'ChanghuaCounty', 
    'NantouCounty', 'YunlinCounty', 'ChiayiCounty', 
    'PingtungCounty', 'YilanCounty', 'HualienCounty', 
    'TaitungCounty', 'KinmenCounty'
];

// 为每个城市创建集合
cities.forEach(city => {
    if (!db.getCollectionNames().includes(city)) {
        db.createCollection(city);
        print(`已创建${city}集合`);
    }
});

print('MongoDB初始化完成'); 
'''
Created on 26 sept. 2019

@author: doudz

quick and dirty converter from zigate.json to zigbee.db

'''

import json
import sqlite3
from binascii import unhexlify

JSON = 'zigate.json'
DB = 'zigbee.db'


def create_db(cursor):
    tables = [
        'CREATE TABLE IF NOT EXISTS attributes (ieee ieee, endpoint_id, cluster, attrid, value)',
        'CREATE TABLE IF NOT EXISTS clusters (ieee ieee, endpoint_id, cluster)',
        'CREATE TABLE IF NOT EXISTS devices (ieee ieee, nwk, status)',
        'CREATE TABLE IF NOT EXISTS endpoints (ieee ieee, endpoint_id, profile_id, device_type device_type, status)',
        ('CREATE TABLE IF NOT EXISTS group_members (group_id, ieee ieee, endpoint_id, FOREIGN KEY(group_id) '
         'REFERENCES groups(group_id), FOREIGN KEY(ieee, endpoint_id) REFERENCES endpoints(ieee, endpoint_id))'),
        'CREATE TABLE IF NOT EXISTS groups (group_id, name)',
        'CREATE TABLE IF NOT EXISTS node_descriptors (ieee ieee, value, FOREIGN KEY(ieee) REFERENCES devices(ieee))',
        'CREATE TABLE IF NOT EXISTS output_clusters (ieee ieee, endpoint_id, cluster)',
        ]
    for query in tables:
        cursor.execute(query)

    indexes = [
        'CREATE UNIQUE INDEX IF NOT EXISTS attribute_idx ON attributes(ieee, endpoint_id, cluster, attrid)',
        'CREATE UNIQUE INDEX IF NOT EXISTS cluster_idx ON clusters(ieee, endpoint_id, cluster)',
        'CREATE UNIQUE INDEX IF NOT EXISTS endpoint_idx ON endpoints(ieee, endpoint_id)',
        'CREATE UNIQUE INDEX IF NOT EXISTS group_idx ON groups(group_id)',
        'CREATE UNIQUE INDEX IF NOT EXISTS group_members_idx ON group_members(group_id, ieee, endpoint_id)',
        'CREATE UNIQUE INDEX IF NOT EXISTS ieee_idx ON devices(ieee)',
        'CREATE UNIQUE INDEX IF NOT EXISTS node_descriptors_idx ON node_descriptors(ieee)',
        'CREATE UNIQUE INDEX IF NOT EXISTS output_cluster_idx ON output_clusters(ieee, endpoint_id, cluster)',
        ]
    for query in indexes:
        cursor.execute(query)


conn = sqlite3.connect(DB)
cursor = conn.cursor()
create_db(cursor)

with open(JSON, 'rb') as fp:
    zigate_db = json.load(fp)

for device in zigate_db.get('devices', []):
    query = 'INSERT OR IGNORE INTO devices (ieee, nwk, status) VALUES (?, ?, ?)'
    nwk = int(device['info']['addr'], 16)
    ieee = device['info']['ieee']
    ieee = ':'.join([ieee[i: i+2] for i in range(0, len(ieee), 2)])
    print('Import device ', ieee)
    cursor.execute(query, (ieee, nwk, 2))
    for endpoint in device.get('endpoints', []):
        query = ('INSERT OR IGNORE INTO endpoints (ieee, endpoint_id, profile_id, device_type, status) '
                 'VALUES (?, ?, ?, ?, ?)')
        cursor.execute(query, (ieee, endpoint['endpoint'], endpoint['profile'], endpoint['device'], 1))
        for cluster in endpoint['in_clusters']:
            query = 'INSERT OR IGNORE INTO clusters (ieee, endpoint_id, cluster) VALUES (?, ?, ?)'
            cursor.execute(query, (ieee, endpoint['endpoint'], cluster))
        for cluster in endpoint['out_clusters']:
            query = 'INSERT OR IGNORE INTO output_clusters (ieee, endpoint_id, cluster) VALUES (?, ?, ?)'
            cursor.execute(query, (ieee, endpoint['endpoint'], cluster))
        for cluster in endpoint['clusters']:
            for attribute in cluster['attributes']:
                if 'data' not in attribute:
                    continue
                data = attribute['data']
                if 'value' in attribute and type(attribute['data']) == str and \
                   type(attribute['data']) != type(attribute['value']):
                    data = unhexlify(data)
                query = ('INSERT OR IGNORE INTO attributes (ieee, endpoint_id, cluster, attrid, value) '
                         'VALUES (?, ?, ?, ?, ?)')
                cursor.execute(query, (ieee, endpoint['endpoint'], cluster['cluster'], attribute['attribute'], data))

conn.commit()
conn.close()
print('Conversion done.')

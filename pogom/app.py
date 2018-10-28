#!/usr/bin/python
# -*- coding: utf-8 -*-

import calendar
import logging
import gc
import os

import time
from datetime import datetime, timedelta
from s2sphere import LatLng
from bisect import bisect_left
from flask import Flask, abort, jsonify, render_template, request,\
    make_response, send_from_directory, json, send_file
from flask.json import JSONEncoder
from flask_compress import Compress

from pogom.dyn_img import get_gym_icon, get_pokemon_icon
from .models import (Pokemon, Gym, GymDetails, Pokestop, Raid, ScannedLocation,
                     MainWorker, WorkerStatus, Token, HashKeys,
                     SpawnPoint, DeviceWorker, SpawnpointDetectionData, ScanSpawnPoint, PokestopMember)
from .utils import (get_args, get_pokemon_name, get_pokemon_types,
                    now, dottedQuadToNum, date_secs, clock_between)
from .client_auth import check_auth
from .transform import transform_from_wgs_to_gcj
from .blacklist import fingerprints, get_ip_blacklist
from .customLog import printPokemon

log = logging.getLogger(__name__)
compress = Compress()


def convert_pokemon_list(pokemon):
    args = get_args()
    # Performance:  disable the garbage collector prior to creating a
    # (potentially) large dict with append().
    gc.disable()

    pokemon_result = []
    for p in pokemon:
        p['pokemon_name'] = get_pokemon_name(p['pokemon_id'])
        p['pokemon_types'] = get_pokemon_types(p['pokemon_id'])
        p['encounter_id'] = str(p['encounter_id'])
        if args.china:
            p['latitude'], p['longitude'] = \
                transform_from_wgs_to_gcj(p['latitude'], p['longitude'])
        pokemon_result.append(p)

    # Re-enable the GC.
    gc.enable()
    return pokemon


class Pogom(Flask):

    def __init__(self, import_name, **kwargs):
        self.db_update_queue = kwargs.get('db_update_queue')
        kwargs.pop('db_update_queue')
        self.wh_update_queue = kwargs.get('wh_update_queue')
        kwargs.pop('wh_update_queue')
        self.args = kwargs.get('args')
        kwargs.pop('args')
        super(Pogom, self).__init__(import_name, **kwargs)
        compress.init_app(self)

        args = get_args()

        # Global blist
        if not args.disable_blacklist:
            log.info('Retrieving blacklist...')
            self.blacklist = get_ip_blacklist()
            # Sort & index for binary search
            self.blacklist.sort(key=lambda r: r[0])
            self.blacklist_keys = [
                dottedQuadToNum(r[0]) for r in self.blacklist
            ]
        else:
            log.info('Blacklist disabled for this session.')
            self.blacklist = []
            self.blacklist_keys = []

        self.user_auth_code_cache = {}

        # Routes
        self.json_encoder = CustomJSONEncoder
        self.route("/", methods=['GET'])(self.fullmap)
        self.route("/auth_callback", methods=['GET'])(self.auth_callback)
        self.route("/raw_data", methods=['GET'])(self.raw_data)
        self.route("/loc", methods=['GET'])(self.loc)
        self.route("/scan_loc", methods=['POST'])(self.scan_loc)
        self.route("/teleport_loc", methods=['POST'])(self.teleport_loc)
        self.route("/next_loc", methods=['POST'])(self.next_loc)
        self.route("/mobile", methods=['GET'])(self.list_pokemon)
        self.route("/search_control", methods=['GET'])(self.get_search_control)
        self.route("/search_control", methods=['POST'])(
            self.post_search_control)
        self.route("/stats", methods=['GET'])(self.get_stats)
        self.route("/gym_data", methods=['GET'])(self.get_gymdata)
        self.route("/pokestop_data", methods=['GET'])(self.get_pokestopdata)
        self.route("/submit_token", methods=['POST'])(self.submit_token)
        self.route("/robots.txt", methods=['GET'])(self.render_robots_txt)
        self.route("/webhook", methods=['POST'])(self.webhook)
        self.route("/serviceWorker.min.js", methods=['GET'])(
            self.render_service_worker_js)
        self.route("/feedpokemon", methods=['GET'])(self.feedpokemon)
        self.route("/gym_img", methods=['GET'])(self.gym_img)
        self.route("/pkm_img", methods=['GET'])(self.pokemon_img)

		
    def pokemon_img(self):
        pkm = int(request.args.get('pkm'))
        weather = int(request.args.get('weather')) if 'weather' in request.args else 0
        return send_file(get_pokemon_icon(pkm, weather), mimetype='image/png')

    	
    def gym_img(self):
        team = request.args.get('team')
        level = request.args.get('level')
        raidlevel = request.args.get('raidlevel')
        pkm = request.args.get('pkm')
        is_in_battle = 'in_battle' in request.args
        is_ex_raid_eligible = 'ex_raid' in request.args
        is_unknown = 'is_unknown' in request.args
        return send_file(get_gym_icon(team, level, raidlevel, pkm, is_in_battle, is_ex_raid_eligible, is_unknown), mimetype='image/png')


    def get_pokemon_rarity_code(self, pokemonid):
        rarity = self.get_pokemon_rarity(pokemonid)
        rarities = {
            "New Spawn": 0,
            "Common": 1,
            "Uncommon": 2,
            "Rare": 3,
            "Very Rare": 4,
            "Ultra Rare": 5
        }
        return rarities.get(rarity, 0)

    def get_pokemon_rarity(self, pokemonid):
        rarity = "New Spawn"
        root_path = self.args.root_path
        rarities_path = os.path.join(root_path, 'static/dist/data/rarity.json')
        with open(rarities_path) as f:
            data = json.load(f)
            rarity = data.get(str(pokemonid), "New Spawn")

        return rarity

    def feedpokemon(self):
        self.heartbeat[0] = now()
        args = get_args()
        if args.on_demand_timeout > 0:
            self.control_flags['on_demand'].clear()
        d = {}

        # Request time of this request.
        d['timestamp'] = datetime.utcnow()

        # Request time of previous request.
        if request.args.get('timestamp'):
            timestamp = int(request.args.get('timestamp'))
            timestamp -= 1000  # Overlap, for rounding errors.
        else:
            timestamp = 0

        swLat = request.args.get('swLat')
        swLng = request.args.get('swLng')
        neLat = request.args.get('neLat')
        neLng = request.args.get('neLng')

        oSwLat = request.args.get('oSwLat')
        oSwLng = request.args.get('oSwLng')
        oNeLat = request.args.get('oNeLat')
        oNeLng = request.args.get('oNeLng')

        lastpokemon = request.args.get('lastpokemon')

        weathertypes = {
            0: {
                "name": "None"
            },
            1: {
                "name": "Clear",
                "emoji": u"\u2600",
                "boost": "grass,ground,fire"
            },
            2: {
                "name": "Rainy",
                "emoji": u"\u2614",
                "boost": "water,electric,bug"
            },
            3: {
                "name": "PartlyCloudy",
                "emoji": u"\U0001F324",
                "boost": "normal,rock"
            },
            4: {
                "name": "Overcast",
                "emoji": u"\u2601",
                "boost": "fairy,fighting,poison"
            },
            5: {
                "name": "Windy",
                "emoji": u"\U0001F32C",
                "boost": "dragon,flying,psychic"
            },
            6: {
                "name": "Snow",
                "emoji": u"\u2744",
                "boost": "ice,steel"
            },
            7: {
                "name": "Fog",
                "emoji": u"\U0001F32B",
                "boost": "dark,ghost"
            }
        }

        if request.args.get('pokemon', 'true') == 'true':
            d['lastpokemon'] = request.args.get('pokemon', 'true')

        # If old coords are not equal to current coords we have moved/zoomed!
        if (oSwLng < swLng and oSwLat < swLat and
                oNeLat > neLat and oNeLng > neLng):
            newArea = False  # We zoomed in no new area uncovered.
        elif not (oSwLat == swLat and oSwLng == swLng and
                  oNeLat == neLat and oNeLng == neLng):
            newArea = True
        else:
            newArea = False

        # Pass current coords as old coords.
        d['oSwLat'] = swLat
        d['oSwLng'] = swLng
        d['oNeLat'] = neLat
        d['oNeLng'] = neLng

        if (request.args.get('pokemon', 'true') == 'true' and
                not args.no_pokemon):

            # Exclude ids of Pokemon that are hidden.
            eids = []
            request_eids = request.args.get('eids')
            if request_eids:
                eids = {int(i) for i in request_eids.split(',')}

            if request.args.get('ids'):
                request_ids = request.args.get('ids').split(',')
                ids = [int(x) for x in request_ids if int(x) not in eids]
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active_by_id(ids, swLat, swLng, neLat, neLng))
            elif lastpokemon != 'true':
                # If this is first request since switch on, load
                # all pokemon on screen.
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active(
                        swLat, swLng, neLat, neLng, exclude=eids))
            else:
                # If map is already populated only request modified Pokemon
                # since last request time.
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active(
                        swLat, swLng, neLat, neLng,
                        timestamp=timestamp, exclude=eids))
                if newArea:
                    # If screen is moved add newly uncovered Pokemon to the
                    # ones that were modified since last request time.
                    d['pokemons'] = d['pokemons'] + (
                        convert_pokemon_list(
                            Pokemon.get_active(
                                swLat,
                                swLng,
                                neLat,
                                neLng,
                                exclude=eids,
                                oSwLat=oSwLat,
                                oSwLng=oSwLng,
                                oNeLat=oNeLat,
                                oNeLng=oNeLng)))

            if request.args.get('reids'):
                reids = [int(x) for x in request.args.get('reids').split(',')]
                d['pokemons'] = d['pokemons'] + (
                    convert_pokemon_list(
                        Pokemon.get_active_by_id(reids, swLat, swLng, neLat,
                                                 neLng)))
                d['reids'] = reids

        if request.args.get('seen', 'false') == 'true':
            d['seen'] = Pokemon.get_seen(int(request.args.get('duration')))

        if request.args.get('appearances', 'false') == 'true':
            d['appearances'] = Pokemon.get_appearances(
                request.args.get('pokemonid'),
                int(request.args.get('duration')))

        if request.args.get('appearancesDetails', 'false') == 'true':
            d['appearancesTimes'] = (
                Pokemon.get_appearances_times_by_spawnpoint(
                    request.args.get('pokemonid'),
                    request.args.get('spawnpoint_id'),
                    int(request.args.get('duration'))))

        result = ""
        for pokemon in d['pokemons']:
            if result != "":
                result += "\n"
            result += str(round(pokemon['latitude'], 5)) + "," + str(round(pokemon['longitude'], 5)) + "," + str(pokemon['pokemon_id']) + "," + str(pokemon['pokemon_name'])
            if pokemon['weather_boosted_condition'] > 0 and weathertypes[pokemon['weather_boosted_condition']]:
                result += ", " + weathertypes[pokemon['weather_boosted_condition']]["emoji"] + " " + weathertypes[pokemon['weather_boosted_condition']]["name"]
            rarity = self.get_pokemon_rarity(pokemon['pokemon_id'])
            result += ", " + rarity
            now_date = datetime.utcnow()
            ttl = int(round((pokemon['disappear_time'] - now_date).total_seconds() / 60))
            result += ", " + str(ttl) + "m"

        return result.strip()

    def render_robots_txt(self):
        return render_template('robots.txt')

    def render_service_worker_js(self):
        return send_from_directory('static/dist/js', 'serviceWorker.min.js')

    def get_coords(self, pokemon_dict, pokestops_dict, gyms_dict):
        minlat = None
        maxlat = None
        minlong = None
        maxlong = None

        if pokemon_dict:
            for p in pokemon_dict:
                if not minlat or p['lat'] < minlat:
                    minlat = p['lat']
                if not maxlat or p['lat'] > maxlat:
                    maxlat = p['lat']
                if not minlong or p['lon'] < minlong:
                    minlong = p['lon']
                if not maxlong or p['lon'] > maxlong:
                    maxlong = p['lon']

        if pokestops_dict:
            for p in pokestops_dict:
                if not minlat or p['latitude'] < minlat:
                    minlat = p['latitude']
                if not maxlat or p['latitude'] > maxlat:
                    maxlat = p['latitude']
                if not minlong or p['longitude'] < minlong:
                    minlong = p['longitude']
                if not maxlong or p['longitude'] > maxlong:
                    maxlong = p['longitude']

        if gyms_dict:
            for p in gyms_dict:
                if not minlat or p['latitude'] < minlat:
                    minlat = p['latitude']
                if not maxlat or p['latitude'] > maxlat:
                    maxlat = p['latitude']
                if not minlong or p['longitude'] < minlong:
                    minlong = p['longitude']
                if not maxlong or p['longitude'] > maxlong:
                    maxlong = p['longitude']

        if not minlat:
            return self.current_location[0], self.current_location[1]

        latitude = round((minlat + maxlat) / 2, 5)
        longitude = round((minlong + maxlong) / 2, 5)

        return latitude, longitude

    def webhook(self):
        request_json = request.get_json()
        pokestops = request_json.get('pokestops')
        pokemon = request_json.get('pokemon')
        gyms = request_json.get('gyms')
        nearby_pokemon = request_json.get('nearby_pokemon')

        uuid = request_json.get('uuid')
        if uuid == "":
            return ""

        lat = float(request_json.get('latitude', request_json.get('latitude:', 0)))
        lng = float(request_json.get('longitude', request_json.get('longitude:', 0)))

        if lat == 0 and lng == 0:
            lat, lng = self.get_coords(pokemon, pokestops, gyms)

        if not self.args.dont_move_map:
            self.location_queue.put((lat, lng, 0))
            self.set_current_location((lat, lng, 0))
            log.info('Changing next location: %s,%s', lat, lng)

        deviceworker = DeviceWorker.get_by_id(uuid, lat, lng)

        deviceworker['scans'] = deviceworker['scans'] + 1
        deviceworker['last_scanned'] = datetime.utcnow()
        if (abs(deviceworker['centerlatitude'] - lat) > (deviceworker['radius'] + 100) * self.args.stepsize or abs(deviceworker['centerlongitude'] - lng) > (deviceworker['radius'] + 100) * self.args.stepsize):
            deviceworker['centerlatitude'] = lat
            deviceworker['centerlongitude'] = lng
            deviceworker['radius'] = 0
            deviceworker['step'] = 0
            deviceworker['direction'] = "U"
            deviceworker['latitude'] = lat
            deviceworker['longitude'] = lng

        deviceworkers = {}
        deviceworkers[uuid] = deviceworker

        self.db_update_queue.put((DeviceWorker, deviceworkers))

        return self.parse_map(pokemon, pokestops, gyms, nearby_pokemon, deviceworker)

    def parse_map(self, pokemon_dict, pokestops_dict, gyms_dict, nearby_pokemon_dict, deviceworker):
        pokemon = {}
        nearby_pokemons = {}
        pokestops = {}
        gyms = {}
        gym_details = {}
        raids = {}
        skipped = 0
        filtered = 0
        stopsskipped = 0
        forts = []
        forts_count = 0
        wild_pokemon = []
        wild_pokemon_count = 0
        nearby_pokemon = 0
        spawn_points = {}
        scan_spawn_points = {}
        sightings = {}
        new_spawn_points = []
        sp_id_list = []

        now_date = datetime.utcnow()

        now_secs = date_secs(now_date)

        scan_location = ScannedLocation.get_by_loc([deviceworker['latitude'], deviceworker['longitude']])

        done_already = scan_location['done']
        ScannedLocation.update_band(scan_location, now_date)
        just_completed = not done_already and scan_location['done']

        if pokemon_dict:
            encounter_ids = [p['id'] for p in pokemon_dict]
            # For all the wild Pokemon we found check if an active Pokemon is in
            # the database.
            with Pokemon.database().execution_context():
                query = (Pokemon
                         .select(Pokemon.encounter_id, Pokemon.spawnpoint_id)
                         .where((Pokemon.disappear_time >= now_date) &
                                (Pokemon.encounter_id << encounter_ids))
                         .dicts())

                # Store all encounter_ids and spawnpoint_ids for the Pokemon in
                # query.
                # All of that is needed to make sure it's unique.
                encountered_pokemon = [
                    (p['encounter_id'], p['spawnpoint_id']) for p in query]

            for p in pokemon_dict:
                spawn_id = p['spawn_id']

                sp = SpawnPoint.get_by_id(spawn_id, p['lat'], p['lon'])
                sp['last_scanned'] = datetime.utcnow()
                spawn_points[spawn_id] = sp
                sp['missed_count'] = 0

                sighting = {
                    'encounter_id': p['id'],
                    'spawnpoint_id': spawn_id,
                    'scan_time': now_date,
                    'tth_secs': None
                }

                # Keep a list of sp_ids to return.
                sp_id_list.append(spawn_id)

                # time_till_hidden_ms was overflowing causing a negative integer.
                # It was also returning a value above 3.6M ms.
                if 0 < p['despawn_time'] < 3600000:
                    d_t_secs = date_secs(datetime.utcfromtimestamp(
                        now() + p['despawn_time'] / 1000.0))

                    # Cover all bases, make sure we're using values < 3600.
                    # Warning: python uses modulo as the least residue, not as
                    # remainder, so we don't apply it to the result.
                    residue_unseen = sp['earliest_unseen'] % 3600
                    residue_seen = sp['latest_seen'] % 3600

                    if (residue_seen != residue_unseen or
                            not sp['last_scanned']):
                        log.info('TTH found for spawnpoint %s.', sp['id'])
                        sighting['tth_secs'] = d_t_secs

                        # Only update when TTH is seen for the first time.
                        # Just before Pokemon migrations, Niantic sets all TTH
                        # to the exact time of the migration, not the normal
                        # despawn time.
                        sp['latest_seen'] = d_t_secs
                        sp['earliest_unseen'] = d_t_secs

                scan_spawn_points[len(scan_spawn_points)+1] = {
                    'spawnpoint': sp['id'],
                    'scannedlocation': scan_location['cellid']}
                if not sp['last_scanned']:
                    log.info('New Spawn Point found.')
                    new_spawn_points.append(sp)

                sp['last_scanned'] = datetime.utcnow()

                if ((p['id'], spawn_id) in encountered_pokemon):
                    # If Pokemon has been encountered before don't process it.
                    skipped += 1
                    continue

                disappear_time = datetime.utcfromtimestamp(p['despawn_time'] / 1000.0)

                start_end = SpawnPoint.start_end(sp, 1)
                seconds_until_despawn = (start_end[1] - now_secs) % 3600
                #disappear_time = now_date + \
                #    timedelta(seconds=seconds_until_despawn)

                pokemon_id = p['type']

                printPokemon(pokemon_id, p['lat'], p['lon'],
                             disappear_time)

                # Scan for IVs/CP and moves.
                pokemon_info = False

                pokemon[p['id']] = {
                    'encounter_id': p['id'],
                    'spawnpoint_id': spawn_id,
                    'pokemon_id': pokemon_id,
                    'latitude': p['lat'],
                    'longitude': p['lon'],
                    'disappear_time': disappear_time,
                    'individual_attack': None,
                    'individual_defense': None,
                    'individual_stamina': None,
                    'move_1': None,
                    'move_2': None,
                    'cp': None,
                    'cp_multiplier': None,
                    'height': None,
                    'weight': None,
                    'gender': p['gender'],
                    'costume': p['costume'],
                    'form': p.get('form', 0),
#                    'weather_id': p.get('weather', None),
                    'weather_boosted_condition': p.get('weather', None)
                }
                if pokemon[p['id']]['costume'] < -1:
                    pokemon[p['id']]['costume'] = -1
                if pokemon[p['id']]['form'] < -1:
                    pokemon[p['id']]['form'] = -1

                if 'pokemon' in self.args.wh_types:
                    if (pokemon_id in self.args.webhook_whitelist or
                        (not self.args.webhook_whitelist and pokemon_id
                         not in self.args.webhook_blacklist)):
                        wh_poke = pokemon[p['id']].copy()
                        wh_poke.update({
                            'disappear_time': calendar.timegm(
                                disappear_time.timetuple()),
                            'last_modified_time': now(),
                            'time_until_hidden_ms': p['despawn_time'],
                            'verified': SpawnPoint.tth_found(sp),
                            'seconds_until_despawn': seconds_until_despawn,
                            'spawn_start': start_end[0],
                            'spawn_end': start_end[1],
                            'player_level': 30,
                            'individual_attack': 0,
                            'individual_defense': 0,
                            'individual_stamina': 0,
                            'move_1': 0,
                            'move_2': 0,
                            'cp': 0,
                            'cp_multiplier': 0,
                            'height': 0,
                            'weight': 0,
                            'weather_id': p.get('weather', None)
                        })

                        rarity = self.get_pokemon_rarity_code(pokemon_id)
                        wh_poke.update({
                            'rarity' : rarity
                        })

                        self.wh_update_queue.put(('pokemon', wh_poke))

        if pokestops_dict:
            stop_ids = [f['pokestop_id'] for f in pokestops_dict]
            if stop_ids:
                with Pokemon.database().execution_context():
                    query = (Pokestop.select(
                        Pokestop.pokestop_id, Pokestop.last_modified).where(
                            (Pokestop.pokestop_id << stop_ids)).dicts())
                    encountered_pokestops = [(f['pokestop_id'], int(
                        (f['last_modified'] - datetime(1970, 1, 1)).total_seconds()))
                                             for f in query]

            for f in pokestops_dict:
                if f['lure_expiration'] > 0:
                    lure_expiration = (datetime.utcfromtimestamp(
                        f['lure_expiration'] / 1000.0) +
                        timedelta(minutes=self.args.lure_duration))
                else:
                    lure_expiration = None
                if f['active_pokemon_id'] > 0:
                    active_pokemon_id = f['active_pokemon_id']
                else:
                    active_pokemon_id = None

                if ((f['pokestop_id'], int(f['last_modified'] / 1000.0))
                        in encountered_pokestops):
                    # If pokestop has been encountered before and hasn't
                    # changed don't process it.
                    stopsskipped += 1
                    continue
                pokestops[f['pokestop_id']] = {
                    'pokestop_id': f['pokestop_id'],
                    'enabled': f['enabled'],
                    'latitude': f['latitude'],
                    'longitude': f['longitude'],
                    'last_modified': datetime.utcfromtimestamp(
                        f['last_modified'] / 1000.0),
                    'lure_expiration': lure_expiration,
                    'active_fort_modifier': active_pokemon_id
                }

                # Send all pokestops to webhooks.
                if 'pokestop' in self.args.wh_types or (
                        'lure' in self.args.wh_types and
                        lure_expiration is not None):
                    l_e = None
                    if lure_expiration is not None:
                        l_e = calendar.timegm(lure_expiration.timetuple())
                    wh_pokestop = pokestops[f['pokestop_id']].copy()
                    wh_pokestop.update({
                        'pokestop_id': f['pokestop_id'],
                        'last_modified': f['last_modified'],
                        'lure_expiration': l_e,
                    })
                    self.wh_update_queue.put(('pokestop', wh_pokestop))

        if gyms_dict:
            stop_ids = [f['gym_id'] for f in gyms_dict]
            for f in gyms_dict:
                b64_gym_id = str(f['gym_id'])
                park = Gym.get_gyms_park(f['gym_id'])

                if 'gym' in self.args.wh_types:
                    raid_active_until = 0
                    raid_battle_ms = f['raidBattleMs']
                    raid_end_ms = f['raidEndMs']

                    if raid_battle_ms / 1000 > time.time():
                        raid_active_until = raid_end_ms / 1000

                    # Explicitly set 'webhook_data', in case we want to change
                    # the information pushed to webhooks.  Similar to above
                    # and previous commits.
                    self.wh_update_queue.put(('gym', {
                        'gym_id':
                            b64_gym_id,
                        'team_id':
                            f['team'],
                        'park':
                            park,
                        'guard_pokemon_id':
                            f['guardingPokemonIdentifier'],
                        'slots_available':
                            f['slotsAvailble'],
                        'total_cp':
                            0,
                        'enabled':
                            f['enabled'],
                        'latitude':
                            f['latitude'],
                        'longitude':
                            f['longitude'],
                        'lowest_pokemon_motivation':
                            0,
                        'occupied_since':
                            calendar.timegm((datetime.utcnow()).timetuple()),
                        'last_modified':
                            f['lastModifiedTimestampMs'],
                        'raid_active_until':
                            raid_active_until
                    }))

                gyms[f['gym_id']] = {
                    'gym_id':
                        f['gym_id'],
                    'team_id':
                        f['team'],
                    'park':
                        park,
                    'guard_pokemon_id':
                        f['guardingPokemonIdentifier'],
                    'slots_available':
                        f['slotsAvailble'],
                    'total_cp':
                        0,
                    'enabled':
                        f['enabled'],
                    'latitude':
                        f['latitude'],
                    'longitude':
                        f['longitude'],
                    'last_modified':
                        datetime.utcfromtimestamp(
                            f['lastModifiedTimestampMs'] / 1000.0),
                    'is_in_battle':
                        f.get('isInBattle', False),
                    'is_ex_raid_eligible':
                        f.get('isExRaidEligible', False)
                }

                gym_id = f['gym_id']

                gymdetails = Gym.get_gym_details(gym_id)
                gym_name = str(f['latitude']) + ',' + str(f['longitude'])
                gym_description = ""
                gym_url = f['imageURL']
                if gymdetails:
                    gym_name = gymdetails.get("name", gym_name)
                    gym_description = gymdetails.get("description", gym_description)
                    gym_url = gymdetails["url"] if gymdetails["url"] != "" else gym_url

                gym_details[gym_id] = {
                    'gym_id': gym_id,
                    'name': gym_name,
                    'description': gym_description,
                    'url': gym_url
                }

                if f['raidSpawnMs'] > 0:
                    raids[f['gym_id']] = {
                        'gym_id': f['gym_id'],
                        'level': f['raidLevel'],
                        'spawn': datetime.utcfromtimestamp(
                            f['raidSpawnMs'] / 1000.0),
                        'start': datetime.utcfromtimestamp(
                            f['raidBattleMs'] / 1000.0),
                        'end': datetime.utcfromtimestamp(
                            f['raidEndMs'] / 1000.0),
                        'pokemon_id': f['raidPokemon'] if f['raidPokemon'] > 0 else None,
                        'cp': None,
                        'move_1': None,
                        'move_2': None
                    }

                    if ('egg' in self.args.wh_types and
                            f['raidPokemon'] == 0) or (
                                'raid' in self.args.wh_types and
                                f['raidPokemon'] > 0):
                        wh_raid = raids[f['gym_id']].copy()
                        wh_raid.update({
                            'gym_id': b64_gym_id,
                            'team_id': f['team'],
                            'spawn': f['raidSpawnMs'] / 1000,
                            'start': f['raidBattleMs'] / 1000,
                            'end': f['raidEndMs'] / 1000,
                            'latitude': f['latitude'],
                            'longitude': f['longitude'],
                            'cp': 0,
                            'move_1': 0,
                            'move_2': 0,
                            'is_ex_raid_eligible' :
                                f.get('isExRaidEligible', False)
                        })
                        self.wh_update_queue.put(('raid', wh_raid))

            del forts

        if nearby_pokemon_dict:
            nearby_pokemon = len(nearby_pokemon_dict)
            nearby_encounter_ids = [p['encounter_id'] for p in nearby_pokemon_dict]
            # For all the wild Pokemon we found check if an active Pokemon is in
            # the database.
            with PokestopMember.database().execution_context():
                query = (PokestopMember
                         .select(PokestopMember.encounter_id, PokestopMember.pokestop_id)
                         .where((PokestopMember.disappear_time >= now_date) &
                                (PokestopMember.encounter_id << nearby_encounter_ids))
                         .dicts())

                # Store all encounter_ids and spawnpoint_ids for the Pokemon in
                # query.
                # All of that is needed to make sure it's unique.
                nearby_encountered_pokemon = [
                    (p['encounter_id'], p['pokestop_id']) for p in query]

            for p in nearby_pokemon_dict:
                pokestop_id = p['fort_id']
                if ((p['encounter_id'], pokestop_id) in nearby_encountered_pokemon):
                    # If Pokemon has been encountered before don't process it.
                    skipped += 1
                    continue

                disappear_time = now_date + timedelta(seconds=600)

                pokemon_id = p['pokemon_id']

                distance = round(p.get('distance', 0), 5)

                nearby_pokemons[p['encounter_id']] = {
                    'encounter_id': p['encounter_id'],
                    'pokestop_id' : p['fort_id'],
                    'pokemon_id': pokemon_id,
                    'disappear_time': disappear_time,
                    'gender': p['gender'],
                    'costume': p['costume'],
                    'form': p.get('form', 0),
                    'weather_boosted_condition': p.get('weather', None),
                    'distance': distance
                }
                if nearby_pokemons[p['encounter_id']]['costume'] < -1:
                    nearby_pokemons[p['encounter_id']]['costume'] = -1
                if nearby_pokemons[p['encounter_id']]['form'] < -1:
                    nearby_pokemons[p['encounter_id']]['form'] = -1

        log.info('Parsing found Pokemon: %d (%d filtered), nearby: %d, ' +
                 'pokestops: %d, gyms: %d, raids: %d.',
                 len(pokemon) + skipped,
                 filtered,
                 nearby_pokemon,
                 len(pokestops) + stopsskipped,
                 len(gyms),
                 len(raids))

        self.db_update_queue.put((ScannedLocation, {0: scan_location}))

        if pokemon:
            self.db_update_queue.put((Pokemon, pokemon))
        if pokestops:
            self.db_update_queue.put((Pokestop, pokestops))
        if gyms:
            self.db_update_queue.put((Gym, gyms))
        if gym_details:
            self.db_update_queue.put((GymDetails, gym_details))
        if raids:
            self.db_update_queue.put((Raid, raids))
        if spawn_points:
            self.db_update_queue.put((SpawnPoint, spawn_points))
            self.db_update_queue.put((ScanSpawnPoint, scan_spawn_points))
            if sightings:
                self.db_update_queue.put((SpawnpointDetectionData, sightings))
        if nearby_pokemons:
            self.db_update_queue.put((PokestopMember, nearby_pokemons))

        return 'ok'

    def submit_token(self):
        response = 'error'
        if request.form:
            token = request.form.get('token')
            query = Token.insert(token=token, last_updated=datetime.utcnow())
            query.execute()
            response = 'ok'
        r = make_response(response)
        r.headers.add('Access-Control-Allow-Origin', '*')
        return r

    def validate_request(self):
        args = get_args()

        # Get real IP behind trusted reverse proxy.
        ip_addr = request.remote_addr
        if ip_addr in args.trusted_proxies:
            ip_addr = request.headers.get('X-Forwarded-For', ip_addr)

        # Make sure IP isn't blacklisted.
        if self._ip_is_blacklisted(ip_addr):
            log.debug('Denied access to %s: blacklisted IP.', ip_addr)
            abort(403)

    def _ip_is_blacklisted(self, ip):
        if not self.blacklist:
            return False

        # Get the nearest IP range
        pos = max(bisect_left(self.blacklist_keys, ip) - 1, 0)
        ip_range = self.blacklist[pos]

        start = dottedQuadToNum(ip_range[0])
        end = dottedQuadToNum(ip_range[1])

        return start <= dottedQuadToNum(ip) <= end

    def set_control_flags(self, control):
        self.control_flags = control

    def set_heartbeat_control(self, heartb):
        self.heartbeat = heartb

    def set_location_queue(self, queue):
        self.location_queue = queue

    def set_current_location(self, location):
        self.current_location = location

    def get_search_control(self):
        return jsonify({
            'status': not self.control_flags['search_control'].is_set()})

    def post_search_control(self):
        args = get_args()
        if not args.search_control or args.on_demand_timeout > 0:
            return 'Search control is disabled', 403
        action = request.args.get('action', 'none')
        if action == 'on':
            self.control_flags['search_control'].clear()
            log.info('Search thread resumed')
        elif action == 'off':
            self.control_flags['search_control'].set()
            log.info('Search thread paused')
        else:
            return jsonify({'message': 'invalid use of api'})
        return self.get_search_control()

    def auth_callback(self, statusname=None):
        return render_template('auth_callback.html')

    def fullmap(self):
        self.heartbeat[0] = now()
        args = get_args()
        if args.on_demand_timeout > 0:
            self.control_flags['on_demand'].clear()

        search_display = False
        scan_display = False

        visibility_flags = {
            'gyms': not args.no_gyms,
            'pokemons': not args.no_pokemon,
            'pokestops': not args.no_pokestops,
            'raids': not args.no_raids,
            'gym_info': args.gym_info,
            'encounter': False,
            'scan_display': scan_display,
            'search_display': search_display,
            'fixed_display': True,
            'custom_css': args.custom_css,
            'custom_js': args.custom_js
        }

        map_lat = self.current_location[0]
        map_lng = self.current_location[1]

        return render_template('map.html',
                               lat=map_lat,
                               lng=map_lng,
                               gmaps_key=args.gmaps_key,
                               lang=args.locale,
                               show=visibility_flags,
                               mapname=args.mapname,
							   generateImages=str(args.generate_images).lower(),
                               )

    def raw_data(self):
        # Make sure fingerprint isn't blacklisted.
        fingerprint_blacklisted = any([
            fingerprints['no_referrer'](request),
            fingerprints['iPokeGo'](request)
        ])

        if fingerprint_blacklisted:
            log.debug('User denied access: blacklisted fingerprint.')
            abort(403)

        self.heartbeat[0] = now()
        args = get_args()
        if args.on_demand_timeout > 0:
            self.control_flags['on_demand'].clear()
        d = {}

        auth_redirect = check_auth(args, request, self.user_auth_code_cache)
        if (auth_redirect):
          return auth_redirect

        # Request time of this request.
        d['timestamp'] = datetime.utcnow()

        # Request time of previous request.
        if request.args.get('timestamp'):
            timestamp = int(request.args.get('timestamp'))
            timestamp -= 1000  # Overlap, for rounding errors.
        else:
            timestamp = 0

        swLat = request.args.get('swLat')
        swLng = request.args.get('swLng')
        neLat = request.args.get('neLat')
        neLng = request.args.get('neLng')

        oSwLat = request.args.get('oSwLat')
        oSwLng = request.args.get('oSwLng')
        oNeLat = request.args.get('oNeLat')
        oNeLng = request.args.get('oNeLng')

        # Previous switch settings.
        lastgyms = request.args.get('lastgyms')
        lastpokestops = request.args.get('lastpokestops')
        lastpokemon = request.args.get('lastpokemon')
        lastslocs = request.args.get('lastslocs')
        lastspawns = request.args.get('lastspawns')

        if request.args.get('luredonly', 'true') == 'true':
            luredonly = True
        else:
            luredonly = False

        # Current switch settings saved for next request.
        if request.args.get('gyms', 'true') == 'true':
            d['lastgyms'] = request.args.get('gyms', 'true')

        if request.args.get('pokestops', 'true') == 'true':
            d['lastpokestops'] = request.args.get('pokestops', 'true')

        if request.args.get('pokemon', 'true') == 'true':
            d['lastpokemon'] = request.args.get('pokemon', 'true')

        if request.args.get('scanned', 'true') == 'true':
            d['lastslocs'] = request.args.get('scanned', 'true')

        if request.args.get('spawnpoints', 'false') == 'true':
            d['lastspawns'] = request.args.get('spawnpoints', 'false')

        # If old coords are not equal to current coords we have moved/zoomed!
        if (oSwLng < swLng and oSwLat < swLat and
                oNeLat > neLat and oNeLng > neLng):
            newArea = False  # We zoomed in no new area uncovered.
        elif not (oSwLat == swLat and oSwLng == swLng and
                  oNeLat == neLat and oNeLng == neLng):
            newArea = True
        else:
            newArea = False

        # Pass current coords as old coords.
        d['oSwLat'] = swLat
        d['oSwLng'] = swLng
        d['oNeLat'] = neLat
        d['oNeLng'] = neLng

        if (request.args.get('pokemon', 'true') == 'true' and
                not args.no_pokemon):

            # Exclude ids of Pokemon that are hidden.
            eids = []
            request_eids = request.args.get('eids')
            if request_eids:
                eids = {int(i) for i in request_eids.split(',')}

            if request.args.get('ids'):
                request_ids = request.args.get('ids').split(',')
                ids = [int(x) for x in request_ids if int(x) not in eids]
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active_by_id(ids, swLat, swLng, neLat, neLng))
            elif lastpokemon != 'true':
                # If this is first request since switch on, load
                # all pokemon on screen.
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active(
                        swLat, swLng, neLat, neLng, exclude=eids))
            else:
                # If map is already populated only request modified Pokemon
                # since last request time.
                d['pokemons'] = convert_pokemon_list(
                    Pokemon.get_active(
                        swLat, swLng, neLat, neLng,
                        timestamp=timestamp, exclude=eids))
                if newArea:
                    # If screen is moved add newly uncovered Pokemon to the
                    # ones that were modified since last request time.
                    d['pokemons'] = d['pokemons'] + (
                        convert_pokemon_list(
                            Pokemon.get_active(
                                swLat,
                                swLng,
                                neLat,
                                neLng,
                                exclude=eids,
                                oSwLat=oSwLat,
                                oSwLng=oSwLng,
                                oNeLat=oNeLat,
                                oNeLng=oNeLng)))

            if request.args.get('reids'):
                reids = [int(x) for x in request.args.get('reids').split(',')]
                d['pokemons'] = d['pokemons'] + (
                    convert_pokemon_list(
                        Pokemon.get_active_by_id(reids, swLat, swLng, neLat,
                                                 neLng)))
                d['reids'] = reids

        if (request.args.get('pokestops', 'true') == 'true' and
                not args.no_pokestops):
            if lastpokestops != 'true':
                d['pokestops'] = Pokestop.get_stops(swLat, swLng, neLat, neLng,
                                                    lured=luredonly)
            else:
                d['pokestops'] = Pokestop.get_stops(swLat, swLng, neLat, neLng,
                                                    timestamp=timestamp)
                if newArea:
                    d['pokestops'].update(
                        Pokestop.get_stops(swLat, swLng, neLat, neLng,
                                           oSwLat=oSwLat, oSwLng=oSwLng,
                                           oNeLat=oNeLat, oNeLng=oNeLng,
                                           lured=luredonly))

        if request.args.get('gyms', 'true') == 'true' and not args.no_gyms:
            if lastgyms != 'true':
                d['gyms'] = Gym.get_gyms(swLat, swLng, neLat, neLng)
            else:
                d['gyms'] = Gym.get_gyms(swLat, swLng, neLat, neLng,
                                         timestamp=timestamp)
                if newArea:
                    d['gyms'].update(
                        Gym.get_gyms(swLat, swLng, neLat, neLng,
                                     oSwLat=oSwLat, oSwLng=oSwLng,
                                     oNeLat=oNeLat, oNeLng=oNeLng))

        if request.args.get('scanned', 'true') == 'true':
            if lastslocs != 'true':
                d['scanned'] = ScannedLocation.get_recent(swLat, swLng,
                                                          neLat, neLng)
            else:
                d['scanned'] = ScannedLocation.get_recent(swLat, swLng,
                                                          neLat, neLng,
                                                          timestamp=timestamp)
                if newArea:
                    d['scanned'] = d['scanned'] + ScannedLocation.get_recent(
                        swLat, swLng, neLat, neLng, oSwLat=oSwLat,
                        oSwLng=oSwLng, oNeLat=oNeLat, oNeLng=oNeLng)

        if request.args.get('seen', 'false') == 'true':
            d['seen'] = Pokemon.get_seen(int(request.args.get('duration')))

        if request.args.get('appearances', 'false') == 'true':
            d['appearances'] = Pokemon.get_appearances(
                request.args.get('pokemonid'),
                int(request.args.get('duration')))

        if request.args.get('appearancesDetails', 'false') == 'true':
            d['appearancesTimes'] = (
                Pokemon.get_appearances_times_by_spawnpoint(
                    request.args.get('pokemonid'),
                    request.args.get('spawnpoint_id'),
                    int(request.args.get('duration'))))

        if request.args.get('spawnpoints', 'false') == 'true':
            if lastspawns != 'true':
                d['spawnpoints'] = SpawnPoint.get_spawnpoints(
                    swLat=swLat, swLng=swLng, neLat=neLat, neLng=neLng)
            else:
                d['spawnpoints'] = SpawnPoint.get_spawnpoints(
                    swLat=swLat, swLng=swLng, neLat=neLat, neLng=neLng,
                    timestamp=timestamp)
                if newArea:
                    d['spawnpoints'] = d['spawnpoints'] + (
                        SpawnPoint.get_spawnpoints(
                            swLat, swLng, neLat, neLng,
                            oSwLat=oSwLat, oSwLng=oSwLng,
                            oNeLat=oNeLat, oNeLng=oNeLng))

        if request.args.get('status', 'false') == 'true':
            args = get_args()
            d = {}
            if args.status_page_password is None:
                d['error'] = 'Access denied'
            elif (request.args.get('password', None) ==
                  args.status_page_password):
                max_status_age = args.status_page_filter
                if max_status_age > 0:
                    d['main_workers'] = MainWorker.get_recent(max_status_age)
                    d['workers'] = WorkerStatus.get_recent(max_status_age)
                else:
                    d['main_workers'] = MainWorker.get_all()
                    d['workers'] = WorkerStatus.get_all()

        return jsonify(d)

    def loc(self):
        d = {}
        d['lat'] = self.current_location[0]
        d['lng'] = self.current_location[1]

        return jsonify(d)

    def teleport_loc(self):
        request_json = request.get_json()

        uuid = request_json.get('uuid')
        if uuid == "":
            return ""

        latitude = round(request_json.get('latitude', 0), 5)
        longitude = round(request_json.get('longitude', 0), 5)

        deviceworker = DeviceWorker.get_by_id(uuid, latitude, longitude)
        if not deviceworker['last_scanned']:
            return "Device need to have posted data first"

        needtojump = False

        last_updated = deviceworker['last_updated']
        last_scanned = deviceworker['last_scanned']
        difference = (last_scanned - last_updated).total_seconds()
        if difference >= 0:
            needtojump = True

        return self.scan_loc(needtojump)

    def scan_loc(self, needtojump=False):
        request_json = request.get_json()

        uuid = request_json.get('uuid')
        if uuid == "":
            return ""

        lat = float(request_json.get('latitude', request_json.get('latitude:', 0)))
        lng = float(request_json.get('longitude', request_json.get('longitude:', 0)))

        latitude = round(lat, 5)
        longitude = round(lng, 5)

        #if latitude == 0 and longitude == 0:
        #    latitude = round(self.current_location[0], 5)
        #    longitude = round(self.current_location[1], 5)

        deviceworker = DeviceWorker.get_by_id(uuid, latitude, longitude)
        if not deviceworker['last_scanned']:
            return "Device need to have posted data first"

        currentlatitude = round(deviceworker['latitude'], 5)
        currentlongitude = round(deviceworker['longitude'], 5)
        centerlatitude = round(deviceworker['centerlatitude'], 5)
        centerlongitude = round(deviceworker['centerlongitude'], 5)
        radius = deviceworker['radius']
        step = deviceworker['step']
        direction = deviceworker['direction']
        last_updated = deviceworker['last_updated']
        last_scanned = deviceworker['last_scanned']

        if needtojump:
            if direction == "U":
                currentlatitude += self.args.teleport_factor * self.args.stepsize
            elif direction == "R":
                currentlongitude += self.args.teleport_factor * self.args.stepsize
                if abs(currentlongitude - centerlongitude) <  abs(currentlongitude - (centerlongitude + radius * self.args.stepsize)):
                    direction = "U"
                    currentlatitude += self.args.teleport_factor * self.args.stepsize
                    currentlongitude = centerlongitude
                    radius += self.args.teleport_factor
                    step = 0
            elif direction == "D":
                currentlatitude -= self.args.teleport_factor * self.args.stepsize
            elif direction == "L":
                currentlongitude -= self.args.teleport_factor * self.args.stepsize
#        if last_updated < last_scanned:
#        if round(datetime.now().timestamp()) % 3 != 0:
#            return "No need for a new update"

        if latitude != 0 and longitude != 0 and (abs(latitude - currentlatitude) > (radius + self.args.teleport_factor) * self.args.stepsize or abs(longitude - currentlongitude) > (radius + self.args.teleport_factor) * self.args.stepsize):
            centerlatitude = latitude
            centerlongitude = longitude
            radius = 0
            step = 0
            direction = "U"

        if (abs(centerlatitude - currentlatitude) > (radius + self.args.teleport_factor) * self.args.stepsize or abs(centerlongitude - currentlongitude) > (radius + self.args.teleport_factor) * self.args.stepsize):
            centerlatitude = latitude
            centerlongitude = longitude
            radius = 0
            step = 0
            direction = "U"

        step += 1

        if radius == 0:
            radius += 1
        elif direction == "U":
            currentlatitude += self.args.stepsize
            if currentlatitude > centerlatitude + radius * self.args.stepsize:
                currentlatitude -= self.args.stepsize
                direction = "R"
                currentlongitude += self.args.stepsize
                if abs(currentlongitude - centerlongitude) < self.args.stepsize:
                    direction = "U"
                    currentlatitude += self.args.stepsize
                    radius += 1
                    step = 0
        elif direction == "R":
            currentlongitude += self.args.stepsize
            if currentlongitude > centerlongitude + radius * self.args.stepsize:
                currentlongitude -= self.args.stepsize
                direction = "D"
                currentlatitude -= self.args.stepsize
            elif abs(currentlongitude - centerlongitude) < self.args.stepsize:
                direction = "U"
                currentlatitude += self.args.stepsize
                radius += 1
                step = 0
        elif direction == "D":
            currentlatitude -= self.args.stepsize
            if currentlatitude < centerlatitude - radius * self.args.stepsize:
                currentlatitude += self.args.stepsize
                direction = "L"
                currentlongitude -= self.args.stepsize
        elif direction == "L":
            currentlongitude -= self.args.stepsize
            if currentlongitude < centerlongitude - radius * self.args.stepsize:
                currentlongitude += self.args.stepsize
                direction = "U"
                currentlatitude += self.args.stepsize

        if self.args.maxradius > 0 and radius > self.args.maxradius:
            currentlatitude = centerlatitude
            currentlongitude = centerlongitude
            radius = 0
            step = 0
            direction = "U"

        deviceworker['latitude'] = round(currentlatitude, 5)
        deviceworker['longitude'] = round(currentlongitude, 5)
        deviceworker['centerlatitude'] = round(centerlatitude, 5)
        deviceworker['centerlongitude'] = round(centerlongitude, 5)
        deviceworker['radius'] = radius
        deviceworker['step'] = step
        deviceworker['direction'] = direction
        deviceworker['last_updated'] = datetime.utcnow()

        deviceworkers = {}
        deviceworkers[uuid] = deviceworker

        self.db_update_queue.put((DeviceWorker, deviceworkers))

        scan_location = ScannedLocation.get_by_loc([deviceworker['latitude'], deviceworker['longitude']])
        ScannedLocation.update_band(scan_location, deviceworker['last_updated'])
        self.db_update_queue.put((ScannedLocation, {0: scan_location}))

        # log.info(request)

        d = {}
        d['latitude'] = deviceworker['latitude']
        d['longitude'] = deviceworker['longitude']

        return jsonify(d)

    def next_loc(self):
        args = get_args()
        if args.fixed_location:
            return 'Location changes are turned off', 403
        lat = None
        lon = None
        # Part of query string.
        if request.args:
            lat = request.args.get('lat', type=float)
            lon = request.args.get('lon', type=float)
        # From post requests.
        if request.form:
            lat = request.form.get('lat', type=float)
            lon = request.form.get('lon', type=float)

        if not (lat and lon):
            log.warning('Invalid next location: %s,%s', lat, lon)
            return 'bad parameters', 400
        else:
            self.location_queue.put((lat, lon, 0))
            self.set_current_location((lat, lon, 0))
            log.info('Changing next location: %s,%s', lat, lon)
            return self.loc()

    def list_pokemon(self):
        # todo: Check if client is Android/iOS/Desktop for geolink, currently
        # only supports Android.
        pokemon_list = []

        # Allow client to specify location.
        lat = request.args.get('lat', self.current_location[0], type=float)
        lon = request.args.get('lon', self.current_location[1], type=float)
        origin_point = LatLng.from_degrees(lat, lon)

        for pokemon in convert_pokemon_list(
                Pokemon.get_active(None, None, None, None)):
            pokemon_point = LatLng.from_degrees(pokemon['latitude'],
                                                pokemon['longitude'])
            diff = pokemon_point - origin_point
            diff_lat = diff.lat().degrees
            diff_lng = diff.lng().degrees
            direction = (('N' if diff_lat >= 0 else 'S')
                         if abs(diff_lat) > 1e-4 else '') +\
                        (('E' if diff_lng >= 0 else 'W')
                         if abs(diff_lng) > 1e-4 else '')
            entry = {
                'id': pokemon['pokemon_id'],
                'name': pokemon['pokemon_name'],
                'card_dir': direction,
                'distance': int(origin_point.get_distance(
                    pokemon_point).radians * 6366468.241830914),
                'time_to_disappear': '%d min %d sec' % (divmod(
                    (pokemon['disappear_time'] - datetime.utcnow()).seconds,
                    60)),
                'disappear_time': pokemon['disappear_time'],
                'disappear_sec': (
                    pokemon['disappear_time'] - datetime.utcnow()).seconds,
                'latitude': pokemon['latitude'],
                'longitude': pokemon['longitude']
            }
            pokemon_list.append((entry, entry['distance']))
        pokemon_list = [y[0] for y in sorted(pokemon_list, key=lambda x: x[1])]
        args = get_args()
        visibility_flags = {
            'custom_css': args.custom_css,
            'custom_js': args.custom_js
        }

        return render_template('mobile_list.html',
                               pokemon_list=pokemon_list,
                               origin_lat=lat,
                               origin_lng=lon,
                               show=visibility_flags
                               )

    def get_stats(self):
        args = get_args()
        visibility_flags = {
            'custom_css': args.custom_css,
            'custom_js': args.custom_js
        }

        return render_template('statistics.html',
                               lat=self.current_location[0],
                               lng=self.current_location[1],
                               gmaps_key=args.gmaps_key,
                               show=visibility_flags,
                               mapname=args.mapname
                               )

    def get_gymdata(self):
        gym_id = request.args.get('id')
        gym = Gym.get_gym(gym_id)

        return jsonify(gym)

    def get_pokestopdata(self):
        pokestop_id = request.args.get('id')
        pokestop = Pokestop.get_stop(pokestop_id)

        return jsonify(pokestop)


class CustomJSONEncoder(JSONEncoder):

    def default(self, obj):
        try:
            if isinstance(obj, datetime):
                if obj.utcoffset() is not None:
                    obj = obj - obj.utcoffset()
                millis = int(
                    calendar.timegm(obj.timetuple()) * 1000 +
                    obj.microsecond / 1000
                )
                return millis
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)

# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: pogoprotos/data/gym/gym_defender.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from pogoprotos.map.pokemon import motivated_pokemon_pb2 as pogoprotos_dot_map_dot_pokemon_dot_motivated__pokemon__pb2
from pogoprotos.data.player import player_public_profile_pb2 as pogoprotos_dot_data_dot_player_dot_player__public__profile__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='pogoprotos/data/gym/gym_defender.proto',
  package='pogoprotos.data.gym',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n&pogoprotos/data/gym/gym_defender.proto\x12\x13pogoprotos.data.gym\x1a.pogoprotos/map/pokemon/motivated_pokemon.proto\x1a\x32pogoprotos/data/player/player_public_profile.proto\"\xdf\x02\n\x0bGymDefender\x12\x43\n\x11motivated_pokemon\x18\x01 \x01(\x0b\x32(.pogoprotos.map.pokemon.MotivatedPokemon\x12L\n\x11\x64\x65ployment_totals\x18\x02 \x01(\x0b\x32\x31.pogoprotos.data.gym.GymDefender.DeploymentTotals\x12K\n\x16trainer_public_profile\x18\x03 \x01(\x0b\x32+.pogoprotos.data.player.PlayerPublicProfile\x1ap\n\x10\x44\x65ploymentTotals\x12\x11\n\ttimes_fed\x18\x01 \x01(\x05\x12\x13\n\x0b\x62\x61ttles_won\x18\x02 \x01(\x05\x12\x14\n\x0c\x62\x61ttles_lost\x18\x03 \x01(\x05\x12\x1e\n\x16\x64\x65ployment_duration_ms\x18\x04 \x01(\x03\x62\x06proto3')
  ,
  dependencies=[pogoprotos_dot_map_dot_pokemon_dot_motivated__pokemon__pb2.DESCRIPTOR,pogoprotos_dot_data_dot_player_dot_player__public__profile__pb2.DESCRIPTOR,])




_GYMDEFENDER_DEPLOYMENTTOTALS = _descriptor.Descriptor(
  name='DeploymentTotals',
  full_name='pogoprotos.data.gym.GymDefender.DeploymentTotals',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='times_fed', full_name='pogoprotos.data.gym.GymDefender.DeploymentTotals.times_fed', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='battles_won', full_name='pogoprotos.data.gym.GymDefender.DeploymentTotals.battles_won', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='battles_lost', full_name='pogoprotos.data.gym.GymDefender.DeploymentTotals.battles_lost', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='deployment_duration_ms', full_name='pogoprotos.data.gym.GymDefender.DeploymentTotals.deployment_duration_ms', index=3,
      number=4, type=3, cpp_type=2, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=403,
  serialized_end=515,
)

_GYMDEFENDER = _descriptor.Descriptor(
  name='GymDefender',
  full_name='pogoprotos.data.gym.GymDefender',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='motivated_pokemon', full_name='pogoprotos.data.gym.GymDefender.motivated_pokemon', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='deployment_totals', full_name='pogoprotos.data.gym.GymDefender.deployment_totals', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='trainer_public_profile', full_name='pogoprotos.data.gym.GymDefender.trainer_public_profile', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_GYMDEFENDER_DEPLOYMENTTOTALS, ],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=164,
  serialized_end=515,
)

_GYMDEFENDER_DEPLOYMENTTOTALS.containing_type = _GYMDEFENDER
_GYMDEFENDER.fields_by_name['motivated_pokemon'].message_type = pogoprotos_dot_map_dot_pokemon_dot_motivated__pokemon__pb2._MOTIVATEDPOKEMON
_GYMDEFENDER.fields_by_name['deployment_totals'].message_type = _GYMDEFENDER_DEPLOYMENTTOTALS
_GYMDEFENDER.fields_by_name['trainer_public_profile'].message_type = pogoprotos_dot_data_dot_player_dot_player__public__profile__pb2._PLAYERPUBLICPROFILE
DESCRIPTOR.message_types_by_name['GymDefender'] = _GYMDEFENDER
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

GymDefender = _reflection.GeneratedProtocolMessageType('GymDefender', (_message.Message,), dict(

  DeploymentTotals = _reflection.GeneratedProtocolMessageType('DeploymentTotals', (_message.Message,), dict(
    DESCRIPTOR = _GYMDEFENDER_DEPLOYMENTTOTALS,
    __module__ = 'pogoprotos.data.gym.gym_defender_pb2'
    # @@protoc_insertion_point(class_scope:pogoprotos.data.gym.GymDefender.DeploymentTotals)
    ))
  ,
  DESCRIPTOR = _GYMDEFENDER,
  __module__ = 'pogoprotos.data.gym.gym_defender_pb2'
  # @@protoc_insertion_point(class_scope:pogoprotos.data.gym.GymDefender)
  ))
_sym_db.RegisterMessage(GymDefender)
_sym_db.RegisterMessage(GymDefender.DeploymentTotals)


# @@protoc_insertion_point(module_scope)

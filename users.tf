resource "immuta_user" "users" {
  for_each = local.users

  user_id     = each.value.user_id
  name        = each.value.name
  email       = each.value.email
  permissions = each.value.permissions
}

locals {
  # Immuta stores one attribute record per value, so expand
  # `jane = { Region = ["APAC", "EMEA"] }` into one entry per value,
  # keyed "<user>:<attribute>:<value>" (e.g. "jane:Region:APAC").
  user_attributes = {
    for attribute in flatten([
      for user_key, user in local.users : [
        for name, attribute_values in user.attributes : [
          for value in attribute_values : {
            user  = user_key
            name  = name
            value = value
          }
        ]
      ]
    ]) : "${attribute.user}:${attribute.name}:${attribute.value}" => attribute
  }
}

resource "immuta_user_attribute" "attributes" {
  for_each = local.user_attributes

  user_id         = immuta_user.users[each.value.user].user_id
  user_profile_id = immuta_user.users[each.value.user].id
  name            = each.value.name
  value           = each.value.value
}

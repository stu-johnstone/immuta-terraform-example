resource "immuta_user_attribute" "attributes" {
  for_each = {
    for attribute in flatten([
      for attribute_key, attribute_config in local.user_attributes : [
        for value in attribute_config.values : {
          key   = "${attribute_key}:${value}"
          user  = attribute_config.user
          name  = attribute_config.name
          value = value
        }
      ]
    ]) : attribute.key => attribute
  }

  user_id         = immuta_user.users[each.value.user].user_id
  user_profile_id = immuta_user.users[each.value.user].id
  name            = each.value.name
  value           = each.value.value
}

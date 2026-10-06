resource "immuta_group" "groups" {
  for_each = local.groups

  name        = each.value.name
  description = each.value.description
  email       = each.value.email
}

locals {
  # One entry per group attribute, keyed "<group>:<attribute>"
  # (e.g. "engineering:Department").
  group_attributes = {
    for attribute in flatten([
      for group_key, group in local.groups : [
        for name, value in group.attributes : {
          group = group_key
          name  = name
          value = value
        }
      ]
    ]) : "${attribute.group}:${attribute.name}" => attribute
  }

  # One entry per group member, keyed "<group>:<user>" (e.g. "engineering:jane").
  group_memberships = {
    for membership in flatten([
      for group_key, group in local.groups : [
        for user_key in group.members : {
          group = group_key
          user  = user_key
        }
      ]
    ]) : "${membership.group}:${membership.user}" => membership
  }
}

resource "immuta_group_attribute" "attributes" {
  for_each = local.group_attributes

  group_id = immuta_group.groups[each.value.group].id
  name     = each.value.name
  value    = each.value.value
}

resource "immuta_group_user" "memberships" {
  for_each = local.group_memberships

  group_id = immuta_group.groups[each.value.group].id
  user_id  = immuta_user.users[each.value.user].user_id
}

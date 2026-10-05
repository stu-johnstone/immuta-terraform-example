resource "immuta_group" "groups" {
  for_each = local.groups

  name        = each.value.name
  description = each.value.description
  email       = each.value.email
}

resource "immuta_group_attribute" "attributes" {
  for_each = local.group_attributes

  group_id = immuta_group.groups[each.value.group].id
  name     = each.value.name
  value    = each.value.value
}

resource "immuta_group_user" "memberships" {
  for_each = {
    for membership in flatten([
      for group, users in local.group_memberships : [
        for user_id in users : {
          key     = "${group}:${user_id}"
          group   = group
          user_id = user_id
        }
      ]
    ]) : membership.key => membership
  }

  group_id = immuta_group.groups[each.value.group].id
  user_id  = each.value.user_id
}

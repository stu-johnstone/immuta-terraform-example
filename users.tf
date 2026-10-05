resource "immuta_user" "users" {
  for_each = local.users

  user_id     = each.value.user_id
  name        = each.value.name
  email       = each.value.email
  permissions = try(each.value.permissions, [])
  disabled    = try(each.value.disabled, false)
}

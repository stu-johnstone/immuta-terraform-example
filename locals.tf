# Example data. Add or change domains, groups and users here; the resources in
# domains.tf, groups.tf and users.tf create one Immuta object per entry.
#
# Map keys (for example `jane` or `engineering`) are stable Terraform
# identifiers. Renaming a key replaces the Immuta object, so treat keys as IDs.

locals {
  domains = {
    research = {
      name        = "Research"
      description = "Domain for the research organisation"
    }

    engineering = {
      name        = "Engineering"
      description = "Domain for the engineering organisation"
    }

    finance = {
      name        = "Finance"
      description = "Domain for the finance organisation"
    }
  }

  users = {
    jane = {
      user_id     = "jane.doe@example.com"
      name        = "Jane Doe"
      email       = "jane.doe@example.com"
      permissions = ["CREATE_PROJECT"]

      # Attribute name => list of values.
      attributes = {
        Department = ["Finance"]
        Region     = ["APAC", "EMEA"]
      }
    }

    ada = {
      user_id     = "ada.lovelace@example.com"
      name        = "Ada Lovelace"
      email       = "ada.lovelace@example.com"
      permissions = []
      attributes  = {}
    }

    alan = {
      user_id     = "alan.turing@example.com"
      name        = "Alan Turing"
      email       = "alan.turing@example.com"
      permissions = []
      attributes  = {}
    }
  }

  groups = {
    engineering = {
      name        = "Engineering"
      description = "Engineering department"
      email       = "engineering@example.com"

      # Keys from local.users.
      members = ["jane", "alan"]

      # Attribute name => value.
      attributes = {
        Department = "Engineering"
      }
    }

    research = {
      name        = "Research"
      description = "Research department"
      email       = "research@example.com"
      members     = ["ada", "jane"]

      attributes = {
        Department = "Research"
      }
    }
  }
}

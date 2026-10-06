# Example data. Add or change entries here; the resources in the other .tf
# files create one Immuta object per entry.
#
# Map keys (for example `jane` or `engineering`) are stable Terraform
# identifiers. Renaming a key replaces the Immuta object, so treat keys as IDs.

locals {
  domains = {
    research = {
      name                  = "Research"
      description           = "Domain for the research organisation"
      reference_identifiers = []
    }

    engineering = {
      name                  = "Engineering"
      description           = "Domain for the engineering organisation"
      reference_identifiers = []
    }

    finance = {
      name        = "Finance"
      description = "Domain for the finance organisation"

      # Keys from local.identifiers. Immuta copies each reference identifier
      # into the domain; the original is left untouched.
      reference_identifiers = ["credit_card"]
    }
  }

  # Key => fully qualified tag name. Tags are hierarchical, and Immuta creates
  # missing parents (here "Discovered").
  tags = {
    credit_card   = "Discovered.Credit card"
    primary_color = "Discovered.Primary color"
  }

  # Identifiers apply tags (keys from local.tags) to matching columns.
  # `domain = null` makes a tenant-wide reference identifier; set it to a key
  # from local.domains to create the identifier inside that domain.
  identifiers = {
    # regex: matches column values.
    credit_card = {
      name        = "Credit card"
      description = "Columns that hold a card number"
      type        = "regex"
      regex       = "[0-9]{16}"
      tags        = ["credit_card"]
      domain      = null
    }

    # columnNameRegex: matches column names instead of their values.
    credit_card_column = {
      name        = "Credit card columns"
      description = "Columns whose name suggests they hold a card number"
      type        = "columnNameRegex"
      regex       = "(card|pan)_?(number|no)"
      tags        = ["credit_card"]
      domain      = null
    }

    # dictionary: matches column values against a fixed list.
    primary_color_dictionary = {
      name           = "Primary color names"
      description    = "Columns that hold one of the primary colors by name"
      type           = "dictionary"
      values         = ["red", "green", "blue"]
      case_sensitive = false
      tags           = ["primary_color"]
      domain         = null
    }

    # Created directly inside the Finance domain.
    finance_primary_color = {
      name        = "Primary colors"
      description = "Columns that hold a primary color"
      type        = "regex"
      regex       = "(red|green|blue)"
      tags        = ["primary_color"]
      domain      = "finance"
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

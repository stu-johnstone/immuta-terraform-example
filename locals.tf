locals {
  environments = {
    non-prod = {
      host = "https://i8xs1yfnyn2g81okkoa1zivf8e.hosted.immutacloud.com/" #"https://non-prod.immuta.example.com"
    }

    prod = {
      host = "https://prod.immuta.example.com"
    }
  }

  environment = local.environments[terraform.workspace]

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

  groups = {
    engineering = {
      name        = "Engineering"
      description = "Engineering department"
      email       = "engineering@example.com"
    }

    research = {
      name        = "Research"
      description = "Research department"
      email       = "research@example.com"
    }
  }

  users = {
    jane = {
      user_id     = "jane.doe@example.com"
      name        = "Jane Doe"
      email       = "jane.doe@example.com"
      permissions = ["CREATE_PROJECT"]
      disabled    = false
    }

    ada = {
      user_id = "ada.lovelace@example.com"
      name    = "Ada Lovelace"
      permissions = []      
      email   = "ada.lovelace@example.com"
    }

    alan = {
      user_id = "alan.turing@example.com"
      name    = "Alan Turing"
      permissions = []      
      email   = "alan.turing@example.com"
    }
  }

  group_memberships = {
    engineering = [
      "jane.doe@example.com",
      "alan.turing@example.com",
    ]

    research = [
      "ada.lovelace@example.com",
      "jane.doe@example.com",
    ]
  }

  group_attributes = {
    engineering_department = {
      group = "engineering"
      name  = "Department"
      value = "Engineering"
    }

    research_department = {
      group = "research"
      name  = "Department"
      value = "Research"
    }
  }

  user_attributes = {
    jane_department = {
      user   = "jane"
      name   = "Department"
      values = ["Finance"]
    }

    jane_regions = {
      user   = "jane"
      name   = "Region"
      values = ["APAC", "EMEA"]
    }
  }
}

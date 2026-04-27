pid_file = "/tmp/agent.pid"

vault {
  address = "http://openbao:8200"
}

# Force re-render des secrets statiques toutes les 5s
# (default 5m -> trop lent pour rotation demo)
template_config {
  static_secret_render_interval = "5s"
}

auto_auth {
  method "approle" {
    config = {
      role_id_file_path                   = "/etc/openbao/role_id"
      secret_id_file_path                 = "/etc/openbao/secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
  sink "file" {
    config = { path = "/run/secrets-rendered/.token" }
  }
}

template {
  source      = "/etc/openbao/app.env.tmpl"
  destination = "/run/secrets-rendered/app.env"
  perms       = "0644"
}

storage "file" {
  path = "/openbao/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

# WSL2/Docker Desktop ne supporte pas mlock, desactive (warning OK pour lab)
disable_mlock = true

api_addr     = "http://0.0.0.0:8200"
cluster_addr = "https://0.0.0.0:8201"

ui = true

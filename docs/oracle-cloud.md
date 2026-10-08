# Implantação na Oracle Cloud Always Free

Este projeto pode rodar em uma VM Ubuntu Always Free da Oracle sem suspensão por inatividade.

## Preparação da VM

1. Crie uma instância Ubuntu 24.04 Always Free.
2. Na lista de segurança da VCN, libere as portas TCP **80** e **22**.
3. Conecte-se por SSH à VM.
4. Instale Docker e o plugin Compose:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER
newgrp docker
```

## Publicação

```bash
git clone -b refactor/remove-bling https://github.com/xJoyceDias/star-limp-ia.git
cd star-limp-ia
mkdir -p data
docker compose -f docker-compose.oracle.yml up -d --build
```

A aplicação ficará em `http://IP_PUBLICO_DA_VM`.

## Banco de dados

O arquivo SQLite é mantido em `./data/starlimp.db` no disco da VM. No primeiro início, o sistema copia o banco-base do repositório. Faça cópias de segurança periódicas de `data/starlimp.db`.

> Para HTTPS e domínio próprio, use um proxy reverso como Caddy depois de apontar o domínio para o IP público da VM.

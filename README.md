# API do claviculário

Este projeto é a parte do servidor de um claviculário de chaves. A API recebe pedidos do site e eventos do ESP32, confere as regras e grava os dados no banco.

## Visão geral

- **Site**: autentica uma pessoa com e-mail e senha; consulta chaves, reservas e empréstimos.
- **ESP32**: autentica o dispositivo com um token secreto; envia o UID do cartão RFID e as chaves retiradas/devolvidas.
- **API Flask**: confere os dados, identifica o usuário pelo cartão e atualiza o banco.
- **MySQL**: mantém usuários, chaves, reservas, eventos do dispositivo e empréstimos.

O ESP32 não precisa conhecer a senha do usuário. Ele lê o cartão e envia seu UID para a API. A API encontra a conta associada ao UID. O UID é apenas um identificador: mantenha também o token secreto do dispositivo e use HTTPS quando a API estiver acessível pela rede.

## Estrutura dos arquivos

| Arquivo | Para que serve |
|---|---|
| `app.py` | Ponto de entrada usado pelo Flask e execução local. |
| `claviculario/__init__.py` | Configura a aplicação, conecta extensões e registra rotas. |
| `claviculario/models.py` | Modelos/tabelas do banco de dados. |
| `claviculario/auth.py` | Login, token e cadastro de usuários. |
| `claviculario/keys.py` | Cadastro e consulta de chaves. |
| `claviculario/reservations.py` | Criação, consulta e cancelamento de reservas. |
| `claviculario/loans.py` | Consulta dos empréstimos. |
| `claviculario/device.py` | Recebimento dos eventos RFID enviados pelo ESP32. |
| `claviculario/extensions.py` e `utils.py` | Extensões compartilhadas e funções auxiliares. |
| `schema.sql` | Criação manual das tabelas no MySQL. |
| `requirements.txt` | Bibliotecas Python necessárias. |
| `.env.example` | Exemplo das configurações secretas e da conexão ao banco. |

## Preparação no Raspberry Pi

Recomendado: Python 3.11 ou mais recente e MySQL 8 ou mais recente.

1. Crie no MySQL um banco e um usuário próprio para a aplicação. Dê ao usuário permissões somente nesse banco.
2. Copie `.env.example` para `.env`.
3. Edite `.env`: preencha a conexão em `DATABASE_URL` e substitua os valores de exemplo de `FLASK_SECRET_KEY`, `JWT_SECRET_KEY` e `DEVICE_TOKEN` por segredos aleatórios.
4. Acrescente ao `.env` os dados do primeiro administrador:

   ```dotenv
   ADMIN_NAME=Administrador
   ADMIN_EMAIL=admin@exemplo.com
   ADMIN_PASSWORD=uma-senha-forte
   ```

5. Crie e ative um ambiente virtual e instale as bibliotecas:

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   No Windows, a ativação é `.venv\\Scripts\\activate`.

6. Crie as tabelas e o administrador inicial:

   ```sh
   flask --app app init-db
   ```

7. Para desenvolvimento na rede local, inicie a API:

   ```sh
   flask --app app run --host 0.0.0.0 --port 5000
   ```

O padrão de desenvolvimento usa SQLite se `DATABASE_URL` não estiver definida. Para o Raspberry Pi, configure a URL MySQL antes de inicializar. Por exemplo:

```dotenv
DATABASE_URL=mysql+pymysql://claviculario:senha@localhost:3306/claviculario?charset=utf8mb4
```

O comando `init-db` cria tabelas usando os modelos Python. Como alternativa, importe `schema.sql` no MySQL e depois rode `flask --app app init-db` para criar o administrador inicial. Se já existir um banco de uma versão anterior sem o campo RFID, aplique uma vez:

```sql
ALTER TABLE users ADD COLUMN rfid_uid VARCHAR(64) NULL UNIQUE;
```

Para disponibilizar a API fora de uma rede de desenvolvimento, use um servidor WSGI e HTTPS. O servidor de desenvolvimento do Flask não é indicado para produção.

## Conceitos principais

### Como o código está organizado

O projeto foi dividido por responsabilidade para ficar mais fácil de acompanhar:

1. `app.py` chama `create_app()` e expõe a variável `app` esperada pelo comando Flask.
2. `claviculario/__init__.py` monta a aplicação, carrega configurações, conecta banco e JWT e registra os grupos de rotas.
3. Cada arquivo de rotas define um Blueprint: um conjunto de URLs relacionado a um assunto.
4. As rotas usam as classes de `models.py` para ler e gravar dados. Funções compartilhadas, como conversão de data, ficam em `utils.py`.

Essa organização não muda os endereços HTTP documentados abaixo; ela apenas separa o código por assunto.

### O caminho de uma requisição

Por exemplo, quando o site consulta `GET /api/keys`:

1. O navegador envia uma requisição HTTP para o Raspberry Pi, junto com o token JWT.
2. Flask compara o caminho e método HTTP com `@bp.get("/api/keys")` em `claviculario/keys.py` e escolhe a função `list_keys`.
3. `@jwt_required()` roda antes da função e rejeita a chamada se o token estiver ausente, inválido ou expirado.
4. A função usa os modelos de `models.py` através de `db` (`extensions.py`) para consultar as chaves e empréstimos no banco.
5. `jsonify(...)` transforma os dados Python em JSON; Flask envia a resposta de volta ao navegador.

Os decoradores `@bp.get`, `@bp.post` e `@bp.delete` conectam uma função a um método e endereço HTTP. `request` é o pedido que chegou ao servidor: `request.get_json()` lê seu corpo e `request.args` lê parâmetros da URL. Uma rota normalmente termina retornando o conteúdo da resposta e, opcionalmente, um código HTTP como `201` (criado), `400` (pedido inválido), `401` (não autenticado), `403` (sem permissão) ou `404` (não encontrado).

### Como Python grava dados no banco

Os modelos são classes Python que representam tabelas. Por exemplo, `User(...)` monta um objeto usuário. `db.session.add(objeto)` prepara a inclusão ou alteração; `db.session.commit()` confirma as mudanças e as envia ao banco. Se ocorrer um erro no meio de uma transação que precisa ser desfeita, `db.session.rollback()` cancela as mudanças pendentes. Consultas como `User.query.filter_by(email=email).first()` significam “procure usuários com este e-mail e devolva o primeiro resultado, ou `None` se não houver”.

`db.relationship(...)` conecta objetos relacionados para que o código possa navegar entre eles. Uma reserva guarda `key_id` e `user_id` (os números das chaves estrangeiras), e os relacionamentos permitem também ler `reservation.key.name` e `reservation.user.name`.

### Como os arquivos se conectam

```text
app.py
  └─ create_app() em claviculario/__init__.py
       ├─ conecta db e jwt de extensions.py
       ├─ registra os Blueprints (auth, keys, reservations, loans, device)
       └─ registra /health e o comando init-db

Blueprint de rota ── usa ──> models.py ── mapeia ──> tabelas MySQL/SQLite
       ├─ usa db/jwt de extensions.py
       └─ usa validações e respostas comuns de utils.py
```

O ponto importante é que `create_app()` reúne as peças. Os arquivos de rotas não criam outro servidor Flask; eles apenas descrevem grupos de endereços, chamados Blueprints, que a aplicação principal registra.

### Usuários e login do site

As senhas são guardadas como hash, não em texto simples. O login retorna um token JWT. O site deve enviar esse token nas rotas protegidas:

```http
Authorization: Bearer TOKEN_RECEBIDO_NO_LOGIN
```

Existem dois papéis: `user` e `admin`. Administradores podem cadastrar usuários e chaves. Usuários podem consultar as chaves e criar reservas. Cada usuário só pode cancelar as próprias reservas, a menos que seja administrador.

O cartão é cadastrado junto ao usuário. Exemplo do corpo de criação de usuário (requer token de administrador):

```json
{
  "name": "Ana Silva",
  "email": "ana@escola.edu",
  "password": "senha-com-pelo-menos-8-caracteres",
  "role": "user",
  "rfid_uid": "04A1B2C3D4"
}
```

`rfid_uid` pode ser omitido na criação, mas sem ele a pessoa não poderá ser reconhecida pelo leitor RFID. O UID é normalizado para maiúsculas e deve ser único.

### Chaves e estado atual

O cadastro administrativo de chave recebe `code` e `name`; `description` e `sensor_id` são opcionais. A rota de consulta usa os empréstimos ainda abertos para informar `available` e `holder_user_id`.

### Reservas

Uma reserva tem chave, usuário, título, início e fim. Os horários devem ser enviados em ISO 8601, preferencialmente com `Z` para UTC, por exemplo `2026-11-20T13:00:00Z`. A API armazena os horários em UTC.

Os intervalos são tratados como início incluso e fim exclusivo: `[início, fim)`. Assim, uma reserva que termina às 14h não conflita com outra que começa às 14h. Reservas confirmadas da mesma chave não podem se sobrepor. A rota de listagem aceita filtros `from`, `to` e `key_id`, úteis para montar uma agenda.

### Mensagens do ESP32

O ESP32 envia o cabeçalho `X-Device-Token` com o valor configurado em `DEVICE_TOKEN`. O JSON contém um `event_id` único, a ação, o UID RFID e os IDs das chaves. Use `withdraw` para retirada e `return` para devolução.

Exemplo de retirada:

```http
POST /api/device/events
X-Device-Token: SEGREDO_DO_DISPOSITIVO
Content-Type: application/json
```

```json
{
  "event_id": "esp32-001-000045",
  "rfid_uid": "04A1B2C3D4",
  "action": "withdraw",
  "key_ids": [3, 4],
  "occurred_at": "2026-11-20T13:05:00Z"
}
```

O `event_id` é criado pelo ESP32 para cada leitura/operação e deve ser mantido igual se o mesmo evento for reenviado por falha de rede. Isso impede que uma repetição crie empréstimos duplicados. Se várias chaves forem enviadas juntas, a API valida todas; se alguma não puder ser retirada/devolvida, nenhuma mudança daquele evento é gravada.

`occurred_at` é opcional. Se omitido, o servidor usa o horário em que recebeu a mensagem. Mantenha o relógio do ESP32 sincronizado (por exemplo, via NTP) se enviar esse campo.

## Rotas disponíveis

| Método | Rota | Quem pode usar | Função |
|---|---|---|---|
| `GET` | `/health` | qualquer cliente | Confirma que a API está respondendo. |
| `POST` | `/api/auth/login` | público | Faz login com `email` e `password`. |
| `GET` | `/api/auth/me` | usuário autenticado | Retorna os dados da conta do token. |
| `POST` | `/api/users` | administrador | Cadastra pessoa, senha, papel e UID RFID opcional. |
| `GET` | `/api/keys` | usuário autenticado | Lista chaves e disponibilidade. |
| `POST` | `/api/keys` | administrador | Cadastra uma chave. |
| `GET` | `/api/reservations` | usuário autenticado | Lista reservas; aceita `from`, `to`, `key_id`. |
| `POST` | `/api/reservations` | usuário autenticado | Cria reserva. |
| `DELETE` | `/api/reservations/{id}` | dono ou administrador | Cancela reserva confirmada. |
| `GET` | `/api/loans?active=true` | usuário autenticado | Lista empréstimos; usuário vê os próprios, admin vê todos. |
| `POST` | `/api/device/events` | ESP32 autenticado | Registra retirada ou devolução pelo RFID. |

## Exemplos de chamadas

### 1. Fazer login

```sh
curl -X POST http://raspberrypi:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@exemplo.com","password":"uma-senha-forte"}'
```

Copie o `access_token` da resposta para usar nas chamadas do site.

### 2. Cadastrar uma chave

```sh
curl -X POST http://raspberrypi:5000/api/keys \
  -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' \
  -d '{"code":"LAB-01","name":"Laboratório 01","sensor_id":"sensor-01"}'
```

### 3. Consultar chaves

```sh
curl http://raspberrypi:5000/api/keys -H 'Authorization: Bearer TOKEN'
```

### 4. Reservar uma chave

```sh
curl -X POST http://raspberrypi:5000/api/reservations \
  -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' \
  -d '{"key_id":1,"title":"Aula de Física","starts_at":"2026-11-20T13:00:00Z","ends_at":"2026-11-20T14:00:00Z"}'
```

## E o LED de reserva?

As rotas atuais permitem que o site consulte as reservas, mas ainda não existe uma rota exclusiva para o ESP32 consultar a agenda usando o token do dispositivo. Para o LED refletir reservas novas, alteradas ou canceladas, o firmware precisará consultar periodicamente uma rota de agenda do dispositivo (polling). Essa rota ainda precisa ser implementada. A consulta pode retornar o estado atual e as próximas reservas de cada chave; assim o ESP32 não precisa manter uma conexão aberta.

## O que este projeto não faz

- Não controla eletricamente a fechadura nem os LEDs; isso é responsabilidade do firmware e do circuito.
- Não decide como o leitor RFID é conectado ao ESP32.
- Não substitui o mecanismo físico por uma verificação online em tempo real: planeje o que acontece se a rede cair.
- O UID simples de alguns cartões RFID pode ser copiado. O token do ESP32 protege a API contra chamadas sem credencial, mas não impede sozinho a clonagem de um cartão.

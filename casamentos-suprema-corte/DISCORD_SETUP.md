# Integração Discord: Suprema Corte Nobre

1. No Discord Developer Portal, crie uma aplicação e abra **OAuth2**.
2. Copie o **Application ID** para `DISCORD_CLIENT_ID` e o **Client Secret** para `DISCORD_CLIENT_SECRET`. Nunca publique o secret.
3. Em **OAuth2 > Redirects**, adicione exatamente `https://casamentos-suprema-corte.onrender.com/auth/discord/callback` (ajuste se o domínio Render for outro).
4. No Discord, habilite **Modo Desenvolvedor**. Clique com botão direito no servidor e **Copiar ID do servidor**. Configure `DISCORD_GUILD_ID`.
5. Clique com botão direito nos cargos permitidos e copie seus IDs. Configure `DISCORD_ALLOWED_ROLE_IDS` com os IDs separados por vírgulas, do cargo mais prioritário ao menos prioritário. Configure `DISCORD_ROLE_NAMES` como JSON com cada ID e nome de cargo.
6. No Render > serviço > **Environment**, adicione as variáveis do `.env.example` com os valores reais. `SECRET_KEY` deve ser fixa, forte e secreta. `COOKIE_SECURE=1` para HTTPS.
7. Envie os arquivos alterados ao GitHub e aguarde o redeploy. Entre em `/admin/login` e clique **Entrar com Discord**.

O OAuth2 usa `identify guilds.members.read` para ler o próprio perfil do usuário e seus cargos naquele servidor. O nome é o apelido do servidor quando existir. Acesso é concedido apenas a IDs de cargo explicitamente autorizados. Os cargos são consultados no login; mudanças posteriores só são refletidas no próximo login. Para revogação imediata, implemente revalidação periódica e expiração de sessão.

**Atenção:** os IDs de cargo e do servidor são números, não nomes. Não envie segredos ao GitHub. O sistema atual ainda usa SQLite local, inadequado para dados permanentes no Render Free. O endpoint `/admin/setup` do projeto original é público até existir um administrador: proteja/desabilite esse cadastro antes do uso oficial.


## Configuração deste servidor

DISCORD_GUILD_ID=1564132096471990412
DISCORD_ALLOWED_ROLE_IDS=1564132484218880151,1564132888146870382,1564134018482704416

O painel exibe apenas nome, avatar e cargo, sem mostrar o ID da conta Discord. Os IDs dos três cargos ainda precisam ser associados aos respectivos nomes. Até isso ser feito, o cargo aparecerá como "Cargo autorizado". Os IDs de cargo são usados apenas internamente para autorizar acesso.


## Nomes dos cargos no painel

No Render, em Environment, configure `DISCORD_ROLE_NAMES` como JSON (não como lista separada por vírgulas):

```json
{"1564132484218880151":"Alta Cúpula","1564132888146870382":"Ministros","1564134018482704416":"Secretários"}
```

A prioridade de exibição é Alta Cúpula, Ministros, Secretários. O ID do Discord não é exibido no painel.

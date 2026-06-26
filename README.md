# Dashboard de intoxicação exógena em idosos

Projeto de análise e visualização sobre notificações de tentativa de suicídio por intoxicação exógena na população idosa, com recortes por sexo, estado e ano.

## Rodando localmente

```bash
poetry install
poetry run python dashboard/run_local.py
```

O script monta os arquivos do dashboard e sobe um servidor local. Depois, abra a URL mostrada no terminal.

## Gerando HTML compartilhavel

```bash
poetry run python dashboard/export_html.py
```

O arquivo gerado fica em `dashboard/dashboard_standalone.html`.

## Gerando a versão para GitHub Pages

```bash
poetry run python dashboard/build_github_pages.py
```

Esse comando cria a pasta `site/`, pronta para deploy estático no GitHub Pages.

## Publicando no GitHub Pages

1. Crie um repositório no GitHub.
2. Adicione o remoto:

```bash
git remote add origin git@github.com:SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

3. No GitHub, abra `Settings > Pages`.
4. Em `Build and deployment`, escolha `GitHub Actions` como source.
5. O workflow `.github/workflows/deploy-pages.yml` vai buildar e publicar o dashboard automaticamente a cada push na branch `main`.

Se o repositório for um project site comum, a URL final tende a ser:

```text
https://SEU_USUARIO.github.io/SEU_REPOSITORIO/
```

Se o repositório se chamar `SEU_USUARIO.github.io`, a URL tende a ser a raiz:

```text
https://SEU_USUARIO.github.io/
```

## Observações importantes

- O GitHub Pages publica arquivos estáticos. Por isso o Python roda no GitHub Actions apenas para gerar os artefatos do site antes do deploy.
- Se você estiver no GitHub Free, o repositório precisa ser público para usar GitHub Pages.
- Revise o conteúdo do repositório antes de publicar. Se houver arquivos sensíveis, remova-os antes do primeiro push.

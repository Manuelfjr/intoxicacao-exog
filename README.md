# Dashboard de intoxicacao exogena em idosos

Projeto de analise e visualizacao sobre notificacoes de tentativa de suicidio por intoxicacao exogena na populacao idosa, com recortes por sexo, estado e ano.

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

## Gerando a versao para GitHub Pages

```bash
poetry run python dashboard/build_github_pages.py
```

Esse comando cria a pasta `site/`, pronta para deploy estatico no GitHub Pages.

## Publicando no GitHub Pages

1. Crie um repositorio no GitHub.
2. Adicione o remoto:

```bash
git remote add origin git@github.com:SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

3. No GitHub, abra `Settings > Pages`.
4. Em `Build and deployment`, escolha `GitHub Actions` como source.
5. O workflow `.github/workflows/deploy-pages.yml` vai buildar e publicar o dashboard automaticamente a cada push na branch `main`.

Se o repositorio for um project site comum, a URL final tende a ser:

```text
https://SEU_USUARIO.github.io/SEU_REPOSITORIO/
```

Se o repositorio se chamar `SEU_USUARIO.github.io`, a URL tende a ser a raiz:

```text
https://SEU_USUARIO.github.io/
```

## Observacoes importantes

- O GitHub Pages publica arquivos estaticos. Por isso o Python roda no GitHub Actions apenas para gerar os artefatos do site antes do deploy.
- Se voce estiver no GitHub Free, o repositorio precisa ser publico para usar GitHub Pages.
- Revise o conteudo do repositorio antes de publicar. Se houver arquivos sensiveis, remova-os antes do primeiro push.

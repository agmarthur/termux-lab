# Publicando no GitHub

Roteiro para colocar o Termux Lab no GitHub do zero.

## 1. Ajuste os créditos e os links

- No `README.md`, troque `<seu-usuario>` pelo seu usuário do GitHub no comando
  de `git clone`.
- Em `LICENSE`, confira o ano e os nomes dos detentores dos direitos.
- Em `vitualizador.desktop`, o campo `Exec=` aponta para o caminho absoluto da
  sua máquina. Para publicar, use um caminho relativo ou explique no README que
  o usuário deve ajustar.

## 2. Crie o repositório local

```bash
cd "/home/ar/Área de trabalho/vitualizador"
git init -b main
git add .
git commit -m "Termux Lab: virtualizador QEMU com interface gráfica"
```

Se o Git reclamar de identidade:

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu@email"
```

## 3. Crie o repositório remoto

Com GitHub CLI:

```bash
gh repo create termux-lab --public --source=. --push
```

Sem GitHub CLI:

1. Abra <https://github.com/new>, nome `termux-lab`, **sem** README e sem
   licença (já existem no projeto).
2. Copie a URL e rode:

```bash
git remote add origin https://github.com/<seu-usuario>/termux-lab.git
git push -u origin main
```

## 4. Ajustes que valem a pena antes do primeiro push

- **Descrição**: “Virtualizador QEMU com interface gráfica em PyQt6 — escolha,
  veja o comando, rode.”
- **Tópicos**: `qemu`, `virtualization`, `pyqt6`, `python`, `emulator`,
  `linux`, `kvm`.
- **Screenshots**: as imagens em `docs/` já aparecem no README.
- **Releases**: crie uma tag depois de estabilizar:

```bash
git tag -a v1.0.0 -m "Primeira versão pública"
git push origin v1.0.0
```

## 5. Checklist de publicação

- [ ] `python3 -m vitualizador --selftest` passa
- [ ] `README.md` sem placeholders (`<seu-usuario>`)
- [ ] `LICENSE` com nomes e ano corretos
- [ ] `.gitignore` evita `__pycache__/` e arquivos locais
- [ ] Screenshots em `docs/` atualizadas
- [ ] Nenhum caminho pessoal sobrando no código ou nos perfis
- [ ] Nenhum segredo, token ou dado pessoal no repositório

## 6. Segurança antes de publicar

```bash
grep -rnE "(senha|password|token|api[_-]?key|secret)" --include="*.py" .
git status --short
```

Confirme também que `~/.config/vitualizador/vms/` **não** foi copiado para
dentro do projeto: os perfis ficam fora da pasta do código.

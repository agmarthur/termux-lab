# Contribuindo

Obrigado pelo interesse. Este projeto é pequeno e direto: uma interface PyQt6
que traduz um perfil de máquina para uma linha de comando do QEMU.

## Antes de tudo

- Leia o [README](README.md) e o [guia de uso](docs/como-usar.md).
- Abra uma *issue* descrevendo o problema ou a ideia antes de mudanças grandes.
- Se for uma arquitetura nova ou um dispositivo que faltou, inclua o comando do
  QEMU que funciona e a versão (`qemu-system-x86_64 --version`).

## Ambiente

```bash
git clone https://github.com/<seu-usuario>/termux-lab.git
cd termux-lab
sudo apt install qemu-system-x86 qemu-img python3-pyqt6
```

## Verificações antes do pull request

```bash
python3 -m py_compile vitualizador/*.py
python3 -m vitualizador --selftest   # gera comandos para todas as arquiteturas instaladas
```

Se mexeu na interface, abra o app e percorra as abas. Se mexeu no
`build.py`, rode também a VM de teste:

```bash
QT_QPA_PLATFORM=offscreen python3 -m vitualizador
```

## Padrões de código

- Python 3.10+, sem dependências além de PyQt6.
- Nomes de variáveis, funções e classes em português; comandos e flags do QEMU
  em inglês (são a API do QEMU).
- Cada opção de interface deve ter um campo correspondente em `VMConfig`, para
  que o perfil continue serializável.
- Todo argumento novo do QEMU entra em `build.py` com uma linha de comentário
  dizendo o que faz.
- Nunca monte strings de shell: `build.py` devolve uma **lista** de argumentos.
- Avisos ao usuário são adicionados em `Plan.warnings`, nunca impressos direto.

## Estrutura das mudanças

| Arquivo | Cuida de |
|---|---|
| `vitualizador/arch.py` | metadados de arquitetura, firmwares, consultas ao QEMU |
| `vitualizador/model.py` | os dados de uma VM (e o JSON do perfil) |
| `vitualizador/build.py` | perfis → argumentos do QEMU |
| `vitualizador/store.py` | perfis em disco, `qemu-img` |
| `vitualizador/ui.py` | janela, abas, execução do processo |
| `vitualizador/theme.py` | tema escuro |
| `vitualizador/splash.py` | tela de abertura |

## Enviando o pull request

1. Crie um branch: `git switch -c feat/sua-mudanca`.
2. Faça commits pequenos, no imperativo (“corrige boot em RISC-V”).
3. Execute as verificações acima.
4. Descreva no PR o que mudou, como testou e quais arquiteturas cobriu.

## Licença das contribuições

Ao contribuir, você concorda que o código entra sob a licença MIT deste
repositório.

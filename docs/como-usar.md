# Como usar o Termux Lab (guia detalhado)

Este documento explica cada campo da interface e o que ele gera no comando do
QEMU. Para instalação e visão geral, veja o [README](../README.md).

## Índice

1. [Primeiro contato](#primeiro-contato)
2. [Aba Sistema](#aba-sistema)
3. [Aba Discos e mídia](#aba-discos-e-mídia)
4. [Aba Rede](#aba-rede)
5. [Aba Vídeo e dispositivos](#aba-vídeo-e-dispositivos)
6. [Aba Avançado](#aba-avançado)
7. [Painel de comando e log](#painel-de-comando-e-log)
8. [Perfis de máquina](#perfis-de-máquina)
9. [Fluxo completo: instalar um Linux](#fluxo-completo-instalar-um-linux)
10. [Fluxo completo: usar depois de instalar](#fluxo-completo-usar-depois-de-instalar)
11. [Avisos do programa](#avisos-do-programa)

---

## Primeiro contato

Ao abrir, aparece a splash do **termux lab** e depois a janela principal:

- **Barra lateral**: lista de máquinas salvas, botões de gerenciamento e o botão
  **▶ Iniciar**.
- **Abas centrais**: tudo o que vai para a linha de comando.
- **Painel inferior**: o comando gerado, os avisos e a saída do QEMU.

O comando é recalculado a cada alteração. Se algo estiver errado, o painel de
avisos explica antes de você tentar rodar.

## Aba Sistema

| Campo | Gera | Dica |
|---|---|---|
| Nome da VM | `-name` | também vira o nome do arquivo de perfil |
| Arquitetura | binário `qemu-system-*` | veja a tabela do README |
| Máquina (chipset) | `-machine` | `q35` para PCs modernos; `virt` em ARM/RISC-V |
| CPU | `-cpu` | automático resolve para `host` (KVM) ou `max` (TCG) |
| Acelerador | `accel=` | KVM só na arquitetura nativa |
| Memória | `-m` | aumente antes de instalar sistemas gráficos |
| Processadores | `-smp` | só é enviado quando maior que 1 |
| Firmware | `-bios` / `-drive if=pflash` | UEFI para Windows 11 e ARM64 |
| Kernel / Initrd / Argumentos | `-kernel`, `-initrd`, `-append` | boot direto, dispensa firmware |
| Ordem de boot | `-boot order=` | `d` = CD, `c` = disco, `n` = rede |

Escolher a arquitetura recarrega as listas de máquinas e CPUs a partir do
binário correspondente.

## Aba Discos e mídia

### Criar disco

1. **Criar disco** → escolha onde salvar (padrão `~/Imagens/VMs`).
2. Informe o tamanho em GB.
3. O formato vem da extensão: `.qcow2` → qcow2, `.raw`/`.img` → raw.

O arquivo é criado na hora com `qemu-img` e já anexado à VM. qcow2 cresce sob
demanda e aceita snapshots; raw é mais rápido e simples.

### Anexar disco

Para imagens que você já tem. O formato é lido com `qemu-img info`.

### Detalhes do disco

| Campo | Gera |
|---|---|
| Formato | `format=` |
| Interface | `virtio-blk-pci`, `virtio-scsi` + `scsi-hd`, `if=ide` ou `usb-storage` |
| Somente leitura | `readonly=on` |

### ISOs

**Adicionar ISO** aceita várias. No x86 o CD vai por `ide-cd`; nas outras
arquiteturas, por `virtio-scsi` + `scsi-cd` — que é o caminho com boot
confiável em ARM64, RISC-V e LoongArch.

## Aba Rede

### Modo

- **Sem rede**: `-nic none`.
- **Usuário / NAT**: `-netdev user` — internet funciona sem configurar nada.
- **Bridge**: `-netdev bridge,br=...` — o convidado entra na rede local.
- **TAP**: `-netdev tap,ifname=...` — controle manual.

### Placa

`virtio-net-pci` é o melhor em praticamente todos os casos. `e1000`/`rtl8139`
servem para sistemas antigos que não têm driver VirtIO.

### Regras de porta

Cada linha vira `hostfwd=tcp::<host>-:<convidado>`. Exemplo prático:

| Protocolo | Porta host | Porta convidado | Resultado |
|---|---|---|---|
| tcp | 2222 | 22 | `ssh -p 2222 usuario@127.0.0.1` |
| tcp | 8080 | 80 | `http://127.0.0.1:8080` |

Regras só valem no modo NAT.

## Aba Vídeo e dispositivos

| Opção | Gera | Observação |
|---|---|---|
| Saída de vídeo | `-display` | GTK é a janela nativa; VNC permite acesso remoto |
| Placa de vídeo | `-vga` / `-device virtio-gpu-pci` | automático escolhe o melhor por arquitetura |
| Console serial | `-nographic` | a saída aparece no log e você digita no campo abaixo dele |
| Tablet USB | `-device usb-tablet` | mouse absoluto, sem "capturar cursor" |
| Áudio | `-audiodev pa` + `-device hda-duplex` | apenas x86 nesta versão |
| Snapshot | `-snapshot` | alterações no disco são descartadas ao desligar |
| Relógio local | `-rtc base=localtime` | evita relógio adiantado no Windows |
| Menu de boot | `-boot menu=on` | permite escolher o dispositivo ao iniciar |
| Pasta compartilhada | `-virtfs local,...` | monte com `mount -t 9p -o trans=virtio hostshare /mnt` |

## Aba Avançado

Campo de texto com argumentos crus. Cada linha (ou espaço) vira um argumento.
Use para o que a interface ainda não cobre:

```
-device usb-host,vendorid=0x0781,productid=0x5567
-monitor unix:/tmp/monitor.sock,server,nowait
```

## Painel de comando e log

- **Comando QEMU**: linha final, sempre atualizada. **Copiar** põe no clipboard.
- **Avisos**: em laranja, com o motivo (disco inexistente, IDE em arquitetura
  não-x86, firmware ausente, KVM indisponível…).
- **Testar (2 s)**: executa a configuração sem tela por dois segundos. Se o
  QEMU rejeitar algo, você vê a mensagem imediatamente.
- **Log**: saída padrão e erros do QEMU. Com console serial ligado, use o campo
  de texto abaixo do log para digitar comandos dentro da VM.

## Perfis de máquina

- **Nova**: cria um perfil vazio.
- **Duplicar**: copia tudo, inclusive discos e ISOs anexados.
- **Excluir**: apaga só o perfil; os arquivos de disco permanecem.
- **Salvar configuração**: grava em `~/.config/vitualizador/vms/<nome>.json`.

O app salva automaticamente antes de iniciar e ao fechar.

## Fluxo completo: instalar um Linux

1. **Nova** → nome `Ubuntu 24.04`.
2. Aba **Sistema**: `x86_64`, `q35`, 4096 MB, 2 vCPU.
3. Aba **Discos e mídia**: **Criar disco** → 40 GB em `~/Imagens/VMs`.
4. **Adicionar ISO** → ISO do Ubuntu.
5. Ordem de boot: `CD / ISO primeiro`.
6. **Testar (2 s)** → confirme que não há erro.
7. **▶ Iniciar** → instale normalmente.
8. Ao terminar, exclua a ISO da lista ou troque a ordem para
   `Disco primeiro` e salve.

## Fluxo completo: usar depois de instalar

1. Abra a VM na lista lateral.
2. Rede: NAT + regra `2222 → 22` para SSH.
3. Boot: `Disco primeiro`.
4. **▶ Iniciar**.

## Avisos do programa

| Aviso | Significado | O que fazer |
|---|---|---|
| “Disco não encontrado” | caminho inválido no perfil | reanexe o disco |
| “IDE não existe em …; virou virtio” | IDE só existe em x86 | aceite o virtio ou use SCSI |
| “KVM só acelera a arquitetura nativa” | normal em ARM/RISC-V no PC | espere desempenho de emulação |
| “Firmware padrão ausente” | falta OpenSBI/AAVMF | instale o pacote ou use kernel direto |
| “A máquina X só aceita 1 CPU” | limite da placa emulada | o app já ajusta automaticamente |
| “exige ao menos N MB” | mínimo da arquitetura (ex.: LoongArch) | o app já ajusta automaticamente |

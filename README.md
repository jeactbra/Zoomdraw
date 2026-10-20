# ZoomDraw

Camada de desenho sobre a tela, no estilo do modo desenho do ZoomIt, para Linux Mint Cinnamon (sessão X11).

## Instalação

```sh
./build-deb.sh
sudo dpkg -i zoomdraw_*_all.deb
```

Dependências: `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`, `gir1.2-keybinder-3.0`.

## Uso

O app roda em segundo plano (é iniciado junto com a sessão).

| Comando / tecla | Ação |
|---|---|
| `Ctrl+Shift+1` | mostra/oculta a camada de desenho |
| `zoomdraw desenhar` | mostra/oculta a camada pelo terminal |
| `zoomdraw exit` | encerra o app |
| `Esc` | oculta a camada (o app continua aberto) |
| `r g b y p k` | cor |
| `+` / `-` | espessura |
| `Ctrl+Z` / `e` | desfazer / limpar |
| `h` | mostrar/ocultar a barra |
| `Shift` + arrastar | linha reta |

Log: `~/.cache/zoomdraw.log`.

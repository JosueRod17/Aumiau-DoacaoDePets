document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('pet_form');
    if (!form) return;
    form.dataset.petIdentity = '';
    const wrappers = {
        raca_outra: 'otherBreed', data_nascimento: 'birthDate',
        idade_anos: 'estimatedAge', idade_meses: 'estimatedAge',
    };
    Object.entries(wrappers).forEach(([name, attribute]) => {
        const row = form.querySelector('.field-' + name);
        if (row) row.dataset[attribute] = '';
    });
});

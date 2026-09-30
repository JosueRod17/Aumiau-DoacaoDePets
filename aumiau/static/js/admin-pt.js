// Alguns controles internos do Django ainda não têm tradução em pt-BR.
function traduzirControlesAdmin(root) {
    const valores = {True: 'Sim', False: 'Não', None: 'Não informado'};
    root.querySelectorAll('img[alt]').forEach(img => {
        if (Object.hasOwn(valores, img.alt)) img.alt = valores[img.alt];
    });
    root.querySelectorAll('option').forEach(option => {
        if (option.textContent.trim() === '- Select an option -') option.textContent = 'Selecione uma opção';
    });
    root.querySelectorAll('input[type="file"]:not([data-upload-pt])').forEach(input => {
        if (input.closest('.empty-form')) return;
        input.dataset.uploadPt = '';
        if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', 'Selecionar imagem');
        const wrapper = document.createElement('span');
        wrapper.className = 'aumiau-upload';
        const text = document.createElement('span');
        text.className = 'aumiau-upload__button';
        text.textContent = 'Selecionar arquivo';
        const name = document.createElement('span');
        name.className = 'aumiau-upload__name';
        name.setAttribute('aria-live', 'polite');
        name.textContent = 'Nenhum arquivo selecionado';
        input.before(wrapper);
        wrapper.append(text, input, name);
        input.addEventListener('change', () => {
            name.textContent = Array.from(input.files || []).map(file => file.name).join(', ') || 'Nenhum arquivo selecionado';
        });
    });
}
document.addEventListener('DOMContentLoaded', () => traduzirControlesAdmin(document));
document.addEventListener('formset:added', event => traduzirControlesAdmin(event.target));

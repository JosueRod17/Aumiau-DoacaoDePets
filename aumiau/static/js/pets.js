document.addEventListener('DOMContentLoaded', () => {
    const main = document.querySelector('[data-gallery-main]');
    document.querySelectorAll('[data-gallery-thumbnail]').forEach(link => link.addEventListener('click', event => {
        if (!main) return;
        event.preventDefault();
        main.src = link.href;
        main.alt = link.getAttribute('aria-label');
        document.querySelectorAll('[data-gallery-thumbnail]').forEach(item => item.removeAttribute('aria-current'));
        link.setAttribute('aria-current', 'true');
    }));
    const form = document.querySelector('[data-pet-form], [data-pet-identity]');
    if (!form) return;
    const field = name => form.elements.namedItem(name);
    const value = name => field(name)?.value?.trim() || '';
    const write = (selector, text) => { const el = document.querySelector(selector); if (el) el.textContent = text; };
    const show = (selector, visible) => form.querySelectorAll(selector).forEach(el => { el.hidden = !visible; });
    const catalogue = JSON.parse(document.querySelector('#pet-breed-catalog')?.textContent || '{}');
    field('especie')?.addEventListener('change', () => {
        const options = [['', 'Selecione uma raça ou tipo'], ['Sem raça definida', 'Sem raça definida (vira-lata)'], ['Desconheço', 'Desconheço'], ...(catalogue[value('especie')] || []).map(breed => [breed, breed]), ['__outra__', 'Outra raça ou tipo']];
        field('raca').replaceChildren(...options.map(([key, label]) => new Option(label, key)));
        updatePreview();
    });
    function updatePreview() {
        const estimated = Boolean(field('nascimento_desconhecido')?.checked);
        show('[data-birth-date]', !estimated);
        show('[data-estimated-age]', estimated);
        show('[data-other-breed]', value('raca') === '__outra__');
        if (field('data_nascimento')) field('data_nascimento').disabled = estimated;
        ['idade_anos', 'idade_meses'].forEach(name => { if (field(name)) field(name).disabled = !estimated; });
        if (field('raca_outra')) field('raca_outra').disabled = value('raca') !== '__outra__';
        let years = Number(value('idade_anos')), months = Number(value('idade_meses'));
        let hasAge = estimated && (value('idade_anos') !== '' || value('idade_meses') !== '');
        if (!estimated) {
            const birth = value('data_nascimento');
            hasAge = Boolean(birth);
            if (birth) {
                const [year, month, day] = birth.split('-').map(Number);
                const today = new Date();
                const total = (today.getFullYear() - year) * 12 + today.getMonth() + 1 - month - (today.getDate() < day ? 1 : 0);
                years = Math.floor(Math.max(0, total) / 12);
                months = Math.max(0, total) % 12;
            }
        }
        const age = [years ? years + (years === 1 ? ' ano' : ' anos') : '', months ? months + (months === 1 ? ' mês' : ' meses') : ''].filter(Boolean).join(' e ');
        const size = form.querySelector('input[name="porte"]:checked')?.closest('label')?.textContent.trim();
        const breed = value('raca') === '__outra__' ? value('raca_outra') : value('raca');
        write('[data-preview-name]', value('nome') || 'Nome do pet');
        write('[data-preview-details]', [breed || 'Raça não selecionada', hasAge ? (age || 'Menos de um mês') + (estimated ? ' (estimada)' : '') : 'Idade não informada', size].filter(Boolean).join(' · '));
        write('[data-preview-location]', '📍 ' + (value('cidade') || 'Cidade') + ', ' + (value('estado') || 'UF'));
        const tags = document.querySelector('[data-preview-tags]');
        if (tags) {
            tags.replaceChildren();
            [['vacinado', 'Vacinado'], ['castrado', 'Castrado'], ['vermifugado', 'Vermifugado'], ['microchipado', 'Microchipado'], ['necessidades_especiais', 'Cuidados especiais']].forEach(([name, label]) => {
                if (field(name)?.checked) { const tag = document.createElement('span'); tag.textContent = label; tags.append(tag); }
            });
        }
        show('[data-individual-contact]', !value('ong'));
        show('[data-ong-contact]', Boolean(value('ong')));
        const special = form.querySelector('#id_descricao_necessidades_especiais')?.closest('.pet-field');
        if (special) special.hidden = !field('necessidades_especiais').checked;
    }
    form.addEventListener('input', updatePreview);
    form.addEventListener('change', updatePreview);
    const preview = document.querySelector('[data-main-preview]');
    const originalPhoto = preview?.getAttribute('src') || '';
    const imageUrls = new Map();
    function refreshPhotos(input, selector, principal) {
        const container = form.querySelector(selector);
        if (!container) return;
        (imageUrls.get(input) || []).forEach(url => URL.revokeObjectURL(url));
        const urls = [];
        imageUrls.set(input, urls);
        container.replaceChildren();
        if (principal && preview) {
            if (originalPhoto) preview.src = originalPhoto;
            else preview.removeAttribute('src');
            preview.hidden = !originalPhoto;
            const placeholder = document.querySelector('[data-preview-placeholder]');
            if (placeholder) placeholder.hidden = Boolean(originalPhoto);
        }
        [...input.files].forEach((file, index) => {
            const tile = document.createElement('div');
            tile.className = 'pet-upload-photo';
            if (['image/jpeg', 'image/png'].includes(file.type) && file.size <= 5 * 1024 * 1024) {
                const url = URL.createObjectURL(file);
                urls.push(url);
                const img = document.createElement('img');
                img.src = url; img.alt = 'Prévia de ' + file.name;
                tile.append(img);
                if (principal && preview) {
                    preview.src = url; preview.hidden = false;
                    const placeholder = document.querySelector('[data-preview-placeholder]');
                    if (placeholder) placeholder.hidden = true;
                }
            }
            const filename = document.createElement('small');
            filename.textContent = file.name; tile.append(filename);
            const remove = document.createElement('button');
            remove.type = 'button'; remove.className = 'pet-remove-photo'; remove.textContent = '×';
            remove.setAttribute('aria-label', 'Remover ' + (principal ? 'foto principal' : 'foto ' + (index + 1)) + ': ' + file.name);
            remove.addEventListener('click', () => {
                const remaining = [...input.files].filter((_, current) => current !== index);
                if (!remaining.length) input.value = '';
                else {
                    const transfer = new DataTransfer();
                    remaining.forEach(item => transfer.items.add(item));
                    input.files = transfer.files;
                }
                refreshPhotos(input, selector, principal);
            });
            tile.append(remove); container.append(tile);
        });
    }
    [['[data-preview-main]', '[data-main-upload-preview]', true], ['[data-preview-gallery]', '[data-gallery-preview]', false]].forEach(([inputSelector, outputSelector, principal]) => {
        form.querySelector(inputSelector)?.addEventListener('change', event => refreshPhotos(event.target, outputSelector, principal));
    });
    let sending = false;
    if (form.hasAttribute('data-pet-form') && window.fetch) form.addEventListener('submit', async event => {
        event.preventDefault();
        if (sending) return;
        const data = new FormData(form);
        if (event.submitter?.name) data.set(event.submitter.name, event.submitter.value);
        const alert = form.querySelector('[data-form-errors]');
        alert.replaceChildren(); alert.hidden = true;
        form.querySelectorAll('[data-field-errors]').forEach(el => el.replaceChildren());
        form.querySelectorAll('[aria-invalid]').forEach(el => el.removeAttribute('aria-invalid'));
        sending = true; form.setAttribute('aria-busy', 'true');
        form.querySelectorAll('button[type="submit"]').forEach(button => button.disabled = true);
        try {
            const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}});
            if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sua sessão pode ter expirado. Entre novamente em outra aba e tente enviar. Suas fotos continuam selecionadas nesta página.');
            const result = await response.json();
            if (response.ok && result.redirect_url) { window.location.assign(result.redirect_url); return; }
            if (response.status === 422 && result.errors) {
                alert.textContent = 'Confira os campos indicados. As fotos selecionadas foram mantidas.';
                Object.entries(result.errors).forEach(([name, errors]) => {
                    const box = [...form.querySelectorAll('[data-field-errors]')].find(el => el.dataset.fieldErrors === name);
                    errors.forEach(error => { const p = document.createElement('p'); p.textContent = error.message; (box || alert).append(p); });
                    form.querySelectorAll('[name]').forEach(el => { if (el.name === name) el.setAttribute('aria-invalid', 'true'); });
                });
            } else throw new Error('Não foi possível enviar agora. Suas fotos foram mantidas; tente novamente.');
        } catch (error) {
            alert.textContent = error instanceof TypeError ? 'Falha de conexão. Suas fotos foram mantidas; tente novamente.' : error.message;
        } finally {
            sending = false; form.removeAttribute('aria-busy');
            form.querySelectorAll('button[type="submit"]').forEach(button => button.disabled = false);
        }
        alert.hidden = false; alert.focus();
    });
    updatePreview();
    form.querySelector('[aria-invalid="true"]')?.focus();
});

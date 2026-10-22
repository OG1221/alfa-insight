import {test,expect} from '@playwright/test';
async function nav(page:any,name:string|RegExp){const menu=page.getByRole('button',{name:'Открыть меню',exact:true});if(await menu.isVisible())await menu.click();await page.getByRole('button',{name,exact:true}).click()}
test('company context, filters, real analysis trace and source transparency',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'Важное для вашего бизнеса'})).toBeVisible();
 await expect(page.locator('.article-card').first()).toBeVisible();
 await page.locator('.company-button').click();await page.getByRole('button',{name:/Компания DEMO_U_202/}).click();
 await expect(page.locator('.company-button')).toContainText('DEMO_U_202');
 await nav(page,'Профиль компании');await expect(page.getByRole('heading',{name:'Компания DEMO_U_202'})).toBeVisible();await expect(page.locator('.profile-products')).toContainText('Депозиты');
 await nav(page,/Персональная лента/);
 await page.getByRole('button',{name:'Ставки и финансы',exact:true}).click();await expect(page.locator('.article-card').first()).toBeVisible();
 await expect.poll(async()=>{const values=await page.locator('.article-card .article-meta').allTextContents();return values.length>0&&values.every(t=>t.includes('Ставки и финансы'))}).toBe(true);
 await page.locator('.article-card').first().click();await expect(page.getByRole('heading',{name:'Что произошло',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Позиция Альфа-Банка',exact:true})).toBeVisible();
 await expect(page.getByLabel('Уточняющий вопрос')).toBeDisabled();
 await page.getByRole('button',{name:'Источники',exact:false}).last().click();await expect(page.locator('.evidence-card').first()).toBeVisible();
 await page.getByRole('button',{name:'Как выполнен анализ',exact:true}).click();expect(await page.locator('.trace-list li').count()).toBeGreaterThanOrEqual(10);await expect(page.locator('.trace-view')).toContainText('broaden_search');
 await page.getByRole('button',{name:'Закрыть разбор',exact:true}).click();
 await expect(page.locator('body')).not.toHaveCSS('overflow-x','scroll');
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);expect(overflow).toBe(false);expect(errors).toEqual([]);
});
test('previously unseen text is persisted and analyzed',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Новое событие',exact:true}).click();const title='Проверка новой логистики '+Date.now();
 await page.getByLabel('Заголовок',{exact:true}).fill(title);await page.getByLabel('Текст события',{exact:true}).fill('Учебное неизвестное событие: импорт стали и логистика перевозок могут потребовать пересмотра сроков поставки. Это тестовый ручной ввод.');
 await page.getByRole('button',{name:'Разобрать для компании',exact:false}).click();await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Что проверить дальше',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Закрыть разбор',exact:true}).click();await page.getByLabel('Поиск по событиям',{exact:true}).fill(title);await expect(page.locator('.article-card')).toHaveCount(1);
});
test('SSRF rejection has a readable error',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Новое событие',exact:true}).click();await page.getByRole('button',{name:'По ссылке',exact:true}).click();await page.getByLabel('Ссылка на публикацию',{exact:true}).fill('http://127.0.0.1:5432');await page.getByRole('button',{name:'Разобрать для компании'}).click();await expect(page.getByRole('alert')).toContainText('Разрешены только HTTPS');
});
test('official company access and bank search are gated and work locally',async({page})=>{
 await page.goto('/');await nav(page,'Настройки стенда');await page.getByLabel('Токен локального стенда').fill('alfa-local-admin');await page.getByRole('button',{name:'Открыть данные кейса',exact:true}).click();await expect(page.getByText('Официальный набор · локальный доступ',{exact:true})).toBeVisible();
 await expect(page.locator('.company-button')).toContainText('U_9250');await nav(page,'Аналитика банка');await expect(page.locator('.document-card')).toHaveCount(9);await page.getByLabel('Поиск по банковским материалам').fill('ключевая ставка');await page.getByRole('button',{name:'Найти фрагменты'}).click();await expect(page.locator('.bank-results .panel').first()).toBeVisible();await expect(page.locator('.bank-results .source-link').first()).toHaveAttribute('href',/drive.google.com/);
});

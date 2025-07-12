import requests
from bs4 import BeautifulSoup
import time
import random
import pandas as pd
import io
import zipfile
from urllib.parse import urljoin, urlparse
import re

from flask import Flask, render_template, request, send_file, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_parser_2025_v4.1_secure_random'

def _parse_images_regular(soup, base_url):
    image_urls_for_download = []
    images_for_display = []

    for img in soup.find_all('img'):
        img_src = img.get('src')
        data_src = img.get('data-src')

        final_img_url = None

        if img_src and img_src.strip() and not img_src.strip().startswith('data:'):
            final_img_url = img_src.strip()
        elif data_src and data_src.strip():
            final_img_url = data_src.strip()

        if final_img_url:
            if not final_img_url.startswith('http://') and not final_img_url.startswith('https://'):
                final_img_url = urljoin(base_url, final_img_url)

            if final_img_url not in image_urls_for_download:
                image_urls_for_download.append(final_img_url)
                images_for_display.append(f'<img src="{final_img_url}" alt="изображение" style="max-width:100px; max-height:100px; object-fit:contain;">')

    return image_urls_for_download, images_for_display

def _parse_images_deep(soup, base_url):
    image_urls_for_download, images_for_display = _parse_images_regular(soup, base_url)

    for tag_with_style in soup.find_all(style=True):
        style_attr = tag_with_style.get('style', '')

        match = re.search(r'background-image:\s*url\((.*?)\)', style_attr)

        if match:
            bg_img_raw_url = match.group(1).strip()

            bg_img_url = bg_img_raw_url.strip('"\' ').replace('&quot;', '').replace('&#39;', '')

            if bg_img_url:
                if not bg_img_url.startswith('http://') and not bg_img_url.startswith('https://'):
                    bg_img_url = urljoin(base_url, bg_img_url)

                if bg_img_url not in image_urls_for_download:
                    image_urls_for_download.append(bg_img_url)
                    images_for_display.append(f'<img src="{bg_img_url}" alt="фоновое изображение" style="max-width:100px; max-height:100px; object-fit:contain;">')

    return image_urls_for_download, images_for_display

def parse_website(url, parse_options, deep_parse_mode=False):
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    ]
    headers = {
        'User-Agent': random.choice(user_agents)
    }

    time.sleep(random.uniform(2, 5))

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        data = {}
        all_image_urls_for_download = []

        if parse_options.get('headers'):
            all_headers = []
            for i in range(1, 7):
                for header in soup.find_all(f'h{i}'):
                    text = header.get_text(strip=True)
                    if text:
                        all_headers.append(f'H{i}: {text}')
            data['Заголовки'] = all_headers

        if parse_options.get('links'):
            all_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].strip()]
            data['Ссылки'] = all_links

        if parse_options.get('images'):
            if deep_parse_mode:
                all_image_urls_for_download, all_images_for_display = _parse_images_deep(soup, url)
            else:
                all_image_urls_for_download, all_images_for_display = _parse_images_regular(soup, url)
            data['Изображения'] = all_images_for_display


        if parse_options.get('text_lines'):
            all_paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
            data['Строки текста (P)'] = all_paragraphs

        if parse_options.get('prices'):
            found_prices = [el.get_text(strip=True) for el in soup.find_all(lambda tag: ('price' in tag.get('class', []) or 'cost' in tag.get('class', [])) and tag.get_text(strip=True))]
            if not found_prices:
                price_pattern = re.compile(r'\d[\d,\.]*\s*(?:руб|₽|\$|€|usd|eur|uah)', re.IGNORECASE)
                found_prices = [re.search(price_pattern, tag.get_text(strip=True)).group(0) for tag in soup.find_all(text=price_pattern) if re.search(price_pattern, tag.get_text(strip=True))]
            data['Цены'] = found_prices if found_prices else ['N/A (нужен специфичный селектор)']

        if parse_options.get('description'):
            meta_description = soup.find('meta', attrs={'name': 'description'})
            if meta_description and meta_description.get('content'):
                data['Описание (meta)'] = [meta_description.get('content')]
            else:
                desc_div = soup.find('div', class_='description') or soup.find('div', id='description')
                if desc_div:
                    data['Описание (по тексту)'] = [desc_div.get_text(strip=True)]
                else:
                    data['Описание'] = ['N/A (нужен специфичный селектор)']

        max_len = 0
        if data:
            for key in data:
                if isinstance(data[key], list):
                    max_len = max(max_len, len(data[key]))
            if max_len == 0 and any(data.values()):
                max_len = 1

            for key in data:
                if isinstance(data[key], list):
                    data[key] = data[key] + [None] * (max_len - len(data[key]))
                else:
                    data[key] = [data[key]] + [None] * (max_len - 1)
        else:
            return pd.DataFrame({'Результат': ['Данные не найдены или не выбраны опции парсинга.']}), []

        df = pd.DataFrame(data)
        return df, all_image_urls_for_download

    except requests.exceptions.Timeout:
        flash(f"Ошибка: Время ожидания запроса к {url} истекло. Попробуйте еще раз. Возможно, сайт долго отвечает.", 'error')
        return None, []
    except requests.exceptions.TooManyRedirects:
        flash(f"Ошибка: Слишком много перенаправлений для URL {url}. Проверьте правильность URL.", 'error')
        return None, []
    except requests.exceptions.RequestException as e:
        flash(f"Ошибка при запросе к сайту {url}: {e}. Проверьте URL или попробуйте позже.", 'error')
        return None, []
    except Exception as e:
        flash(f"Произошла непредвиденная ошибка во время парсинга: {e}", 'error')
        return None, []

def manual_parse_website(url, css_selectors_str, xpath_selectors_str):
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    ]
    headers = {
        'User-Agent': random.choice(user_agents)
    }

    time.sleep(random.uniform(1, 3))

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        manual_data = {}
        if css_selectors_str:
            selectors = [s.strip() for s in css_selectors_str.split(',') if s.strip()]
            for selector in selectors:
                found_elements = soup.select(selector)
                if found_elements:
                    manual_data[f'CSS: {selector}'] = [el.get_text(strip=True) for el in found_elements]
                else:
                    manual_data[f'CSS: {selector}'] = ['Элементы не найдены']

        if xpath_selectors_str:
            try:
                from lxml import html
            except ImportError:
                manual_data['Ошибка XPath'] = ['Для использования XPath необходима библиотека lxml. Установите её: pip install lxml']
                flash('Для использования XPath необходимо установить библиотеку lxml: pip install lxml', 'danger')
                return None, None

            tree = html.fromstring(response.content)
            xpath_selectors = [s.strip() for s in xpath_selectors_str.split(',') if s.strip()]
            for selector in xpath_selectors:
                try:
                    found_elements = tree.xpath(selector)
                    if found_elements:
                        extracted_texts = []
                        for el in found_elements:
                            if isinstance(el, html.HtmlElement):
                                extracted_texts.append(el.text_content().strip())
                            elif isinstance(el, str):
                                extracted_texts.append(el.strip())
                            else:
                                extracted_texts.append(str(el).strip())
                        manual_data[f'XPath: {selector}'] = extracted_texts if extracted_texts else ['(Пустое содержимое)']
                    else:
                        manual_data[f'XPath: {selector}'] = ['Элементы не найдены']
                except Exception as e:
                    manual_data[f'XPath: {selector} (Ошибка)'] = [f"Неверный XPath или ошибка: {e}"]
                    flash(f"Ошибка при обработке XPath '{selector}': {e}", 'warning')

        if not manual_data:
            return pd.DataFrame({'Результат': ['Данные по указанным селекторам не найдены.']}), []

        max_len = 0
        for key in manual_data:
            if isinstance(manual_data[key], list):
                max_len = max(max_len, len(manual_data[key]))
        if max_len == 0 and any(manual_data.values()):
            max_len = 1

        for key in manual_data:
            if isinstance(manual_data[key], list):
                manual_data[key] = manual_data[key] + [None] * (max_len - len(manual_data[key]))
            else:
                manual_data[key] = [manual_data[key]] + [None] * (max_len - 1)

        df = pd.DataFrame(manual_data)
        return df, []

    except requests.exceptions.Timeout:
        flash(f"Ошибка: Время ожидания запроса к {url} истекло при ручном парсинге. Попробуйте еще раз.", 'error')
        return None, []
    except requests.exceptions.RequestException as e:
        flash(f"Ошибка при запросе к сайту {url} во время ручного парсинга: {e}. Проверьте URL.", 'error')
        return None, []
    except Exception as e:
        flash(f"Произошла непредвиденная ошибка во время ручного парсинга: {e}", 'error')
        return None, []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        parse_options = {
            'headers': 'headers' in request.form,
            'prices': 'prices' in request.form,
            'description': 'description' in request.form,
            'images': 'images' in request.form,
            'links': 'links' in request.form,
            'text_lines': 'text_lines' in request.form
        }

        if not url:
            flash('Пожалуйста, введите URL.', 'warning')
            return redirect(url_for('index'))

        if not any(parse_options.values()):
            flash('Пожалуйста, выберите хотя бы одну опцию для парсинга.', 'warning')
            return redirect(url_for('index'))

        is_only_images_selected = parse_options.get('images') and \
                                   not parse_options.get('headers') and \
                                   not parse_options.get('prices') and \
                                   not parse_options.get('description') and \
                                   not parse_options.get('links') and \
                                   not parse_options.get('text_lines')

        parsed_data_df, image_urls_for_download = parse_website(url, parse_options, deep_parse_mode=False)

        if parsed_data_df is not None and not parsed_data_df.empty:
            html_table = parsed_data_df.to_html(classes='table table-striped table-bordered', index=False, escape=False)

            session['parsed_html_table'] = html_table
            session['parsed_data_csv'] = parsed_data_df.to_csv(index=False, encoding='utf-8')
            session['last_parsed_url'] = url
            session['parsed_image_urls'] = image_urls_for_download
            session['is_only_images_selected'] = is_only_images_selected
            session['current_image_parsing_mode'] = 'regular'

            return redirect(url_for('results'))
        else:
            session.pop('parsed_html_table', None)
            session.pop('parsed_data_csv', None)
            session.pop('last_parsed_url', None)
            session.pop('parsed_image_urls', None)
            session.pop('is_only_images_selected', None)
            session.pop('current_image_parsing_mode', None)
            return render_template('index.html', url=url)
    return render_template('index.html')

@app.route('/results')
def results():
    html_table = session.get('parsed_html_table')
    last_parsed_url = session.get('last_parsed_url')
    has_images_for_download = bool(session.get('parsed_image_urls'))

    show_deep_parse_button = session.get('is_only_images_selected', False) and \
                             session.get('current_image_parsing_mode') == 'regular'

    if html_table and last_parsed_url:
        return render_template('results.html',
                               url=last_parsed_url,
                               html_table=html_table,
                               has_images=has_images_for_download,
                               show_deep_parse_button=show_deep_parse_button,
                               image_urls=session.get('parsed_image_urls', []),
                               tables_html=None)
    else:
        flash('Нет сохраненных результатов парсинга. Пожалуйста, выполните новый парсинг.', 'info')
        return redirect(url_for('index'))

@app.route('/results/download_csv')
def download_csv():
    csv_data = session.get('parsed_data_csv')
    last_parsed_url = session.get('last_parsed_url', 'unknown_site')

    if csv_data:
        buffer = io.BytesIO(b'\xef\xbb\xbf' + csv_data.encode('utf-8'))
        clean_url = last_parsed_url.replace('http://', '').replace('https://', '').replace('/', '_').replace('.', '_').replace(':', '_').replace('?', '').replace('=', '')
        download_filename = f'parsed_data_{clean_url[:50]}.csv'

        return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=download_filename)
    else:
        flash('Нет данных для скачивания в CSV.', 'error')
        return redirect(url_for('results'))

@app.route('/results/download_images_zip')
def download_images_zip():
    image_urls = session.get('parsed_image_urls')
    last_parsed_url = session.get('last_parsed_url', 'unknown_site')

    if not image_urls:
        flash('Нет картинок для скачивания.', 'error')
        return redirect(url_for('results'))

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        downloaded_count = 0
        for i, img_url in enumerate(image_urls):
            try:
                parsed_url = urlparse(img_url)
                img_name = parsed_url.path.split('/')[-1]
                if '.' in img_name:
                    name_parts = img_name.rsplit('.', 1)
                    img_name = re.sub(r'[^\w\.-]', '', name_parts[0]) + '.' + name_parts[1]
                else:
                    img_name = re.sub(r'[^\w\.-]', '', img_name)

                if not img_name or len(img_name) > 100:
                    img_name = f"image_{i+1}_{random.randint(1000, 9999)}.jpg"

                img_response = requests.get(img_url, timeout=10)
                img_response.raise_for_status()

                zf.writestr(img_name, img_response.content)
                downloaded_count += 1

            except requests.exceptions.Timeout:
                print(f"Предупреждение: Таймаут при скачивании картинки {img_url}. Пропущено.")
            except requests.exceptions.RequestException as e:
                print(f"Ошибка при скачивании картинки {img_url}: {e}. Пропущено.")
            except Exception as e:
                print(f"Непредвиденная ошибка при обработке картинки {img_url}: {e}. Пропущено.")

    memory_file.seek(0)

    if downloaded_count == 0:
        flash('Не удалось скачать ни одной картинки. Возможно, все ссылки недействительны или произошла ошибка.', 'error')
        return redirect(url_for('results'))

    clean_url = last_parsed_url.replace('http://', '').replace('https://', '').replace('/', '_').replace('.', '_').replace(':', '_').replace('?', '').replace('=', '')
    download_filename = f'images_{clean_url[:50]}.zip'

    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=download_filename)

@app.route('/results/deep_parse_images')
def deep_parse_images():
    url_to_reparse = session.get('last_parsed_url')
    if not session.get('is_only_images_selected', False) or session.get('current_image_parsing_mode') == 'deep':
        flash('Глубокий парсинг картинок доступен только если выбрана только опция "Картинки" и еще не выполнен.', 'warning')
        return redirect(url_for('results'))

    if not url_to_reparse:
        flash('Нет URL для глубокого парсинга картинок.', 'error')
        return redirect(url_for('index'))

    parse_options_for_deep_parse = {'images': True, 'headers': False, 'prices': False, 'description': False, 'links': False, 'text_lines': False}

    flash(f"Выполняется глубокий парсинг картинок для {url_to_reparse}...", 'info')
    parsed_data_df, image_urls_for_download = parse_website(url_to_reparse, parse_options_for_deep_parse, deep_parse_mode=True)

    if parsed_data_df is not None and not parsed_data_df.empty:
        html_table = parsed_data_df.to_html(classes='table table-striped table-bordered', index=False, escape=False)

        session['parsed_html_table'] = html_table
        session['parsed_data_csv'] = parsed_data_df.to_csv(index=False, encoding='utf-8')
        session['parsed_image_urls'] = image_urls_for_download
        session['current_image_parsing_mode'] = 'deep'

        flash('Глубокий парсинг картинок успешно завершен!', 'success')
        return redirect(url_for('results'))
    else:
        flash('Не удалось получить данные при глубоком парсинге картинок. Возможно, сайт блокирует запрос.', 'error')
        return redirect(url_for('results'))

@app.route('/manual_parse', methods=['GET', 'POST'])
def manual_parse():
    if request.method == 'POST':
        url = request.form['url']
        css_selectors_input = request.form.get('css_selectors', '').strip()
        xpath_selectors_input = request.form.get('xpath_selectors', '').strip()

        if not url:
            flash('Пожалуйста, введите URL.', 'warning')
            return redirect(url_for('manual_parse'))

        if not css_selectors_input and not xpath_selectors_input:
            flash('Пожалуйста, введите хотя бы один CSS-селектор или XPath.', 'warning')
            return render_template('manual_parse.html', url=url, css_selectors=css_selectors_input, xpath_selectors=xpath_selectors_input)

        flash(f"Выполняется ручной парсинг для {url}...", 'info')
        parsed_manual_df, _ = manual_parse_website(url, css_selectors_input, xpath_selectors_input)

        if parsed_manual_df is not None and not parsed_manual_df.empty:
            manual_html_table = parsed_manual_df.to_html(classes='table table-striped table-bordered', index=False, escape=False)

            session['manual_parsed_html_table'] = manual_html_table
            session['manual_parsed_data_csv'] = parsed_manual_df.to_csv(index=False, encoding='utf-8')
            session['manual_last_parsed_url'] = url

            flash('Ручной парсинг успешно завершен!', 'success')
            return redirect(url_for('manual_results'))
        else:
            return render_template('manual_parse.html', url=url, css_selectors=css_selectors_input, xpath_selectors=xpath_selectors_input)

    initial_url = request.args.get('url', session.get('last_parsed_url', ''))
    return render_template('manual_parse.html', url=initial_url)

@app.route('/manual_results')
def manual_results():
    manual_html_table = session.get('manual_parsed_html_table')
    manual_last_parsed_url = session.get('manual_last_parsed_url')

    if manual_html_table and manual_last_parsed_url:
        return render_template('manual_results.html',
                               url=manual_last_parsed_url,
                               html_table=manual_html_table)
    else:
        flash('Нет сохраненных результатов ручного парсинга. Пожалуйста, выполните новый ручной парсинг.', 'info')
        return redirect(url_for('manual_parse'))

@app.route('/manual_results/download_csv')
def manual_download_csv():
    csv_data = session.get('manual_parsed_data_csv')
    manual_last_parsed_url = session.get('manual_last_parsed_url', 'unknown_site')

    if csv_data:
        buffer = io.BytesIO(b'\xef\xbb\xbf' + csv_data.encode('utf-8'))
        clean_url = manual_last_parsed_url.replace('http://', '').replace('https://', '').replace('/', '_').replace('.', '_').replace(':', '_').replace('?', '').replace('=', '')
        download_filename = f'manual_parsed_data_{clean_url[:50]}.csv'

        return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=download_filename)
    else:
        flash('Нет данных для скачивания в CSV (ручной парсинг).', 'error')
        return redirect(url_for('manual_results'))

if __name__ == '__main__':
    app.run(debug=True)
import re
import requests
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
import pytest


class Links:

    def __init__(self, path_to_links, path_to_movies, tmdb_api_key):
        """
        Объединяет данные из links.csv и movies.csv при помощи встроенных методов и re.
        """
        self.api_key = tmdb_api_key
        self.base_url = "https://api.themoviedb.org/3"

        self.movies_data = {}

        try:
            movies_map = self._parse_movies_csv(path_to_movies)

            self._parse_links_csv(path_to_links, movies_map)

        except Exception as e:
            print(f"Ошибка при инициализации датасетов: {e}")

    def _parse_movies_csv(self, path):
        """
        Парсит movies.csv вручную с помощью регулярных выражений (учитывает запятые внутри кавычек).
        Формат: movieId,title,genres
        """
        movies = {}
        csv_pattern = re.compile(r'(?:^|,)(?:"([^"]*)"|([^,",]*))')

        try:
            with open(path, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                if not lines:
                    return movies

                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue

                    matches = csv_pattern.findall(line)
                    row = [m[0] if m[0] else m[1] for m in matches]

                    if len(row) >= 2:
                        try:
                            movie_id = int(row[0].strip())
                            title = row[1].strip()
                            movies[movie_id] = title
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Ошибка чтения {path}: {e}")

        return movies

    def _parse_links_csv(self, path, movies_map):
        """
        Парсит links.csv.
        Формат: movieId,imdbId,tmdbId
        """
        try:
            with open(path, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                if not lines:
                    return

                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(",")
                    if len(parts) >= 3:
                        try:
                            movie_id = int(parts[0].strip())
                            tmdb_str = parts[2].strip()

                            if tmdb_str:
                                tmdb_id = int(tmdb_str)
                                title = movies_map.get(movie_id, "Unknown Title")

                                self.movies_data[movie_id] = {
                                    "tmdbId": tmdb_id,
                                    "title": title,
                                }
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Ошибка чтения {path}: {e}")

    def _fetch_tmdb_movie_details(self, tmdb_id):
        """
        Безопасный HTTP-запрос к TMDB API.
        """
        url = f"{self.base_url}/movie/{tmdb_id}"
        params = {
            "api_key": self.api_key,
            "append_to_response": "credits",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка HTTP-запроса для tmdbId {tmdb_id}: {e}")
            return None
        except Exception as e:
            print(f"Непредвиденная ошибка при запросе: {e}")
            return None

    def get_imdb(self, list_of_movies, list_of_fields):
        """
        Возвращает список списков [movieId, field1, field2, ...]
        Сортировка по movieId по убыванию.
        """
        results = []

        try:
            for movie_id in list_of_movies:
                if movie_id not in self.movies_data:
                    continue

                tmdb_id = self.movies_data[movie_id]["tmdbId"]
                local_title = self.movies_data[movie_id]["title"]

                data = self._fetch_tmdb_movie_details(tmdb_id)
                if not data:
                    continue

                director = "Unknown"
                if "credits" in data and "crew" in data["credits"]:
                    directors = [
                        m["name"]
                        for m in data["credits"]["crew"]
                        if m.get("job") == "Director"
                    ]
                    if directors:
                        director = ", ".join(directors)

                row_result = [movie_id]

                for field in list_of_fields:
                    if field == "Director":
                        row_result.append(director)
                    elif field == "Budget":
                        row_result.append(data.get("budget", 0))
                    elif field == "Cumulative Worldwide Gross":
                        row_result.append(data.get("revenue", 0))
                    elif field == "Runtime":
                        row_result.append(data.get("runtime", 0))
                    elif field == "Title":
                        row_result.append(data.get("title", local_title))
                    else:
                        row_result.append(None)

                results.append(row_result)

            results.sort(key=lambda x: x[0], reverse=True)

        except Exception as e:
            print(f"Ошибка внутри get_imdb: {e}")

        return results

    def top_directors(self, n):
        """
        dict с top-n режиссерами {режиссер: кол-во фильмов}.
        Сортировка по убыванию.
        """
        directors_count = {}

        try:
            for movie_info in self.movies_data.values():
                data = self._fetch_tmdb_movie_details(movie_info["tmdbId"])
                if not data or "credits" not in data:
                    continue

                for member in data["credits"].get("crew", []):
                    if member.get("job") == "Director":
                        name = member["name"]
                        directors_count[name] = directors_count.get(name, 0) + 1

            sorted_directors = dict(
                sorted(
                    directors_count.items(), key=lambda item: item[1], reverse=True
                )[:n]
            )
            return sorted_directors

        except Exception as e:
            print(f"Ошибка внутри top_directors: {e}")
            return {}

    def most_expensive(self, n):
        """
        dict с top-n фильмов {название: бюджет}.
        Сортировка по убыванию бюджета.
        """
        movie_budgets = {}

        try:
            for movie_info in self.movies_data.values():
                data = self._fetch_tmdb_movie_details(movie_info["tmdbId"])
                if not data:
                    continue

                title = data.get("title") or movie_info["title"]
                budget = data.get("budget", 0)

                if budget > 0:
                    movie_budgets[title] = budget

            sorted_budgets = dict(
                sorted(movie_budgets.items(), key=lambda item: item[1], reverse=True)[
                    :n
                ]
            )
            return sorted_budgets

        except Exception as e:
            print(f"Ошибка внутри most_expensive: {e}")
            return {}

    def most_profitable(self, n):
        """
        dict с top-n фильмов {название: сборы - бюджет}.
        Сортировка по убыванию прибыли.
        """
        movie_profits = {}

        try:
            for movie_info in self.movies_data.values():
                data = self._fetch_tmdb_movie_details(movie_info["tmdbId"])
                if not data:
                    continue

                title = data.get("title") or movie_info["title"]
                budget = data.get("budget", 0)
                revenue = data.get("revenue", 0)

                profit = revenue - budget
                movie_profits[title] = profit

            sorted_profits = dict(
                sorted(movie_profits.items(), key=lambda item: item[1], reverse=True)[
                    :n
                ]
            )
            return sorted_profits

        except Exception as e:
            print(f"Ошибка внутри most_profitable: {e}")
            return {}

    def longest(self, n):
        """
        dict с top-n фильмов {название: хронометраж}.
        Сортировка по убыванию хронометража.
        """
        movie_runtimes = {}

        try:
            for movie_info in self.movies_data.values():
                data = self._fetch_tmdb_movie_details(movie_info["tmdbId"])
                if not data:
                    continue

                title = data.get("title") or movie_info["title"]
                runtime = data.get("runtime", 0) or 0

                if runtime > 0:
                    movie_runtimes[title] = runtime

            sorted_runtimes = dict(
                sorted(
                    movie_runtimes.items(), key=lambda item: item[1], reverse=True
                )[:n]
            )
            return sorted_runtimes

        except Exception as e:
            print(f"Ошибка внутри longest: {e}")
            return {}

    def top_cost_per_minute(self, n):
        """
        dict с top-n фильмов {название: бюджет / хронометраж}, округленный до 2 знаков.
        Сортировка по убыванию.
        """
        costs = {}

        try:
            for movie_info in self.movies_data.values():
                data = self._fetch_tmdb_movie_details(movie_info["tmdbId"])
                if not data:
                    continue

                title = data.get("title") or movie_info["title"]
                budget = data.get("budget", 0)
                runtime = data.get("runtime", 0) or 0

                if budget > 0 and runtime > 0:
                    cost_per_minute = round(budget / runtime, 2)
                    costs[title] = cost_per_minute

            sorted_costs = dict(
                sorted(costs.items(), key=lambda item: item[1], reverse=True)[:n]
            )
            return sorted_costs

        except Exception as e:
            print(f"Ошибка внутри top_cost_per_minute: {e}")
            return {}

class Movies:
    """
    Analyzing data from movies.csv without external heavy libraries (pandas, csv).
    """

    def __init__(self, path_to_the_file):
        """
        Считывает файл movies.csv и сохраняет разобранную структуру.
        Структура элемента self.movies:
        {
            movieId (int): {
                'title': str,
                'year': int или None,
                'genres': list of str
            }
        }
        """
        self.movies = {}

        csv_pattern = re.compile(r'(?:^|,)(?:"([^"]*)"|([^,",]*))')
        year_pattern = re.compile(r"\((\d{4})\)")

        try:
            with open(path_to_the_file, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                if not lines:
                    return

                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue

                    matches = csv_pattern.findall(line)
                    row = [m[0] if m[0] else m[1] for m in matches]

                    if len(row) >= 3:
                        try:
                            movie_id = int(row[0].strip())
                            title = row[1].strip()
                            genres_str = row[2].strip()

                            year = None
                            year_match = year_pattern.search(title)
                            if year_match:
                                year = int(year_match.group(1))

                            genres = (
                                genres_str.split("|")
                                if genres_str and genres_str != "(no genres listed)"
                                else []
                            )

                            self.movies[movie_id] = {
                                "title": title,
                                "year": year,
                                "genres": genres,
                            }
                        except ValueError:
                            continue

        except Exception as e:
            print(f"Ошибка при открытии/чтении файла {path_to_the_file}: {e}")

    def dist_by_release(self):
        """
        Возвращает dict/OrderedDict, где ключи — годы выпуска, а значения — количество фильмов.
        Сортировка по количеству фильмов по убыванию.
        """
        try:
            years = [
                m_info["year"]
                for m_info in self.movies.values()
                if m_info["year"] is not None
            ]
            counts = Counter(years)

            sorted_years = OrderedDict(
                sorted(counts.items(), key=lambda item: item[1], reverse=True)
            )
            return sorted_years
        except Exception as e:
            print(f"Ошибка в dist_by_release: {e}")
            return OrderedDict()

    def dist_by_genres(self):
        """
        Возвращает dict, где ключи — жанры, а значения — количество фильмов с этим жанром.
        Сортировка по количеству по убыванию.
        """
        try:
            all_genres = []
            for m_info in self.movies.values():
                all_genres.extend(m_info["genres"])

            counts = Counter(all_genres)

            sorted_genres = dict(
                sorted(counts.items(), key=lambda item: item[1], reverse=True)
            )
            return sorted_genres
        except Exception as e:
            print(f"Ошибка в dist_by_genres: {e}")
            return {}

    def most_genres(self, n):
        """
        Возвращает dict с top-n фильмов, где ключи — названия фильмов,
        а значения — количество их жанров.
        Сортировка по количеству жанров по убыванию.
        """
        try:
            movie_genre_counts = {}
            for m_info in self.movies.values():
                title = m_info["title"]
                genre_count = len(m_info["genres"])
                movie_genre_counts[title] = genre_count

            sorted_movies = dict(
                sorted(
                    movie_genre_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:n]
            )
            return sorted_movies
        except Exception as e:
            print(f"Ошибка в most_genres: {e}")
            return {}

class Tags:

    def __init__(self, path_to_the_file):
        """
        Считывает файл tags.csv и сохраняет теги.
        """
        self.tags_list = []

        csv_pattern = re.compile(r'(?:^|,)(?:"([^"]*)"|([^,",]*))')

        try:
            with open(path_to_the_file, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                if not lines:
                    return

                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue

                    matches = csv_pattern.findall(line)
                    row = [m[0] if m[0] else m[1] for m in matches]

                    if len(row) >= 3:
                        tag_text = row[2].strip()
                        if tag_text:
                            self.tags_list.append(tag_text)

        except Exception as e:
            print(f"Ошибка при чтении файла {path_to_the_file}: {e}")

    def most_words(self, n):
        """
        Возвращает dict с top-n тегами по количеству слов внутри.
        Удаляет дубликаты тегов. Сортировка по количеству слов по убыванию.
        """
        try:
            unique_tags = set(self.tags_list)

            tag_word_counts = {}
            for tag in unique_tags:
                word_count = len(re.findall(r"\w+", tag))
                tag_word_counts[tag] = word_count

            sorted_tags = dict(
                sorted(
                    tag_word_counts.items(), key=lambda item: item[1], reverse=True
                )[:n]
            )
            return sorted_tags
        except Exception as e:
            print(f"Ошибка в most_words: {e}")
            return {}

    def longest(self, n):
        """
        Возвращает list из top-n самых длинных тегов (по количеству символов).
        Удаляет дубликаты тегов. Сортировка по длине по убыванию.
        """
        try:
            unique_tags = list(set(self.tags_list))

            sorted_tags = sorted(unique_tags, key=lambda tag: len(tag), reverse=True)
            return sorted_tags[:n]
        except Exception as e:
            print(f"Ошибка в longest: {e}")
            return []

    def most_words_and_longest(self, n):
        """
        Возвращает пересечение (list) между top-n тегами с наибольшим числом слов
        и top-n самыми длинными тегами по символам.
        """
        try:
            top_words_tags = set(self.most_words(n).keys())
            top_longest_tags = set(self.longest(n))

            intersection = list(top_words_tags.intersection(top_longest_tags))
            return intersection
        except Exception as e:
            print(f"Ошибка в most_words_and_longest: {e}")
            return []

    def most_popular(self, n):
        """
        Возвращает dict с самыми популярными (часто встречающимися) тегами.
        Ключи — теги, значения — количество упоминаний.
        Сортировка по частоте по убыванию.
        """
        try:
            tag_counts = Counter(self.tags_list)

            sorted_popular = dict(
                sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:n]
            )
            return sorted_popular
        except Exception as e:
            print(f"Ошибка в most_popular: {e}")
            return {}

    def tags_with(self, word):
        """
        Возвращает список всех уникальных тегов, содержащих переданное слово (без учета регистра).
        Сортировка по алфавиту.
        """
        try:
            unique_tags = set(self.tags_list)
            matching_tags = []

            pattern = re.compile(re.escape(word), re.IGNORECASE)

            for tag in unique_tags:
                if pattern.search(tag):
                    matching_tags.append(tag)

            matching_tags.sort()
            return matching_tags
        except Exception as e:
            print(f"Ошибка в tags_with: {e}")
            return []

class Ratings:

    def __init__(self, path_to_ratings, path_to_movies=None):
        """
        Инициализация: считывает ratings.csv и при наличии сопоставляет их с titles из movies.csv
        """
        self.movies_titles = {}
        if path_to_movies:
            self.movies_titles = self._load_movie_titles(path_to_movies)

        self.ratings_data = []

        self.movie_ratings = defaultdict(list)  # {movieId: [rating1, rating2, ...]}
        self.user_ratings = defaultdict(list)  # {userId: [rating1, rating2, ...]}

        self._load_ratings(path_to_ratings)

    def _load_movie_titles(self, path):
        """Парсинг movies.csv для получения сопоставления movieId -> title"""
        titles = {}
        csv_pattern = re.compile(r'(?:^|,)(?:"([^"]*)"|([^,",]*))')
        try:
            with open(path, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    matches = csv_pattern.findall(line)
                    row = [m[0] if m[0] else m[1] for m in matches]
                    if len(row) >= 2:
                        try:
                            m_id = int(row[0].strip())
                            t_title = row[1].strip()
                            titles[m_id] = t_title
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Ошибка при загрузке названий фильмов: {e}")
        return titles

    def _load_ratings(self, path):
        """Парсинг ratings.csv"""
        try:
            with open(path, mode="r", encoding="utf-8") as file:
                lines = file.readlines()
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",")
                    if len(parts) >= 4:
                        try:
                            user_id = int(parts[0].strip())
                            movie_id = int(parts[1].strip())
                            rating = float(parts[2].strip())
                            timestamp = int(parts[3].strip())

                            self.ratings_data.append(
                                (user_id, movie_id, rating, timestamp)
                            )
                            self.movie_ratings[movie_id].append(rating)
                            self.user_ratings[user_id].append(rating)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Ошибка при чтении ratings.csv: {e}")

    class Movies:
        def __init__(self, outer_instance):
            self.outer = outer_instance
            self.data_dict = self.outer.movie_ratings

        def _get_name(self, key_id):
            """Возвращает название фильма по ID"""
            return self.outer.movies_titles.get(key_id, f"Movie_{key_id}")

        @staticmethod
        def _calc_mean(lst):
            """Вычисление среднего арифметического"""
            return sum(lst) / len(lst) if lst else 0.0

        @staticmethod
        def _calc_median(lst):
            """Вычисление медианы"""
            if not lst:
                return 0.0
            s_lst = sorted(lst)
            n = len(s_lst)
            mid = n // 2
            if n % 2 == 1:
                return float(s_lst[mid])
            else:
                return (s_lst[mid - 1] + s_lst[mid]) / 2.0

        @staticmethod
        def _calc_variance(lst):
            """Вычисление несмещенной дисперсии (sample variance)."""
            if len(lst) < 2:
                return 0.0
            mean = sum(lst) / len(lst)
            return sum((x - mean) ** 2 for x in lst) / (len(lst) - 1)

        def dist_by_year(self):
            """
            Возвращает dict {year: count}. Сортировка по годам по возрастанию.
            """
            try:
                years = [
                    datetime.fromtimestamp(ts).year
                    for _, _, _, ts in self.outer.ratings_data
                ]
                counts = Counter(years)
                return dict(sorted(counts.items(), key=lambda x: x[0]))
            except Exception as e:
                print(f"Ошибка в dist_by_year: {e}")
                return {}

        def dist_by_rating(self):
            """
            Возвращает dict {rating: count}. Сортировка по оценке по возрастанию.
            """
            try:
                ratings = [r for _, _, r, _ in self.outer.ratings_data]
                counts = Counter(ratings)
                return dict(sorted(counts.items(), key=lambda x: x[0]))
            except Exception as e:
                print(f"Ошибка в dist_by_rating: {e}")
                return {}

        def top_by_num_of_ratings(self, n):
            """
            Top-n сущностей по количеству оценок. Сортировка по убыванию.
            """
            try:
                counts = {}
                for item_id, r_list in self.data_dict.items():
                    name = self._get_name(item_id)
                    counts[name] = len(r_list)

                sorted_top = dict(
                    sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
                )
                return sorted_top
            except Exception as e:
                print(f"Ошибка в top_by_num_of_ratings: {e}")
                return {}

        def top_by_ratings(self, n, metric="average"):
            """
            Top-n по средней (average) или медианной (median) оценке.
            """
            try:
                metrics_res = {}
                for item_id, r_list in self.data_dict.items():
                    if not r_list:
                        continue

                    if callable(metric):
                        val = metric(r_list)
                    elif metric == "median":
                        val = self._calc_median(r_list)
                    else:
                        val = self._calc_mean(r_list)

                    name = self._get_name(item_id)
                    metrics_res[name] = round(val, 2)

                sorted_top = dict(
                    sorted(metrics_res.items(), key=lambda x: x[1], reverse=True)[:n]
                )
                return sorted_top
            except Exception as e:
                print(f"Ошибка в top_by_ratings: {e}")
                return {}

        def top_controversial(self, n):
            """
            Top-n по дисперсии (variance) оценок.
            """
            try:
                variances = {}
                for item_id, r_list in self.data_dict.items():
                    if len(r_list) > 1:
                        var = self._calc_variance(r_list)
                        name = self._get_name(item_id)
                        variances[name] = round(var, 2)

                sorted_top = dict(
                    sorted(variances.items(), key=lambda x: x[1], reverse=True)[:n]
                )
                return sorted_top
            except Exception as e:
                print(f"Ошибка в top_controversial: {e}")
                return {}

    class Users(Movies):
        """
        Класс для анализа поведения пользователей.
        Наследует методы от Movies, подменяя источник данных и форматирование имён.
        """

        def __init__(self, outer_instance):
            super().__init__(outer_instance)
            self.data_dict = self.outer.user_ratings

        def _get_name(self, key_id):
            """Возвращает userId"""
            return key_id

        def dist_by_num_of_ratings(self):
            """Переиспользует top_by_num_of_ratings из Movies."""
            return self.top_by_num_of_ratings(n=len(self.data_dict))

        def dist_by_user_ratings(self, metric="average"):
            """Переиспользует top_by_ratings из Movies."""
            return self.top_by_ratings(n=len(self.data_dict), metric=metric)

        def top_controversial_users(self, n):
            """Переиспользует top_controversial из Movies."""
            return self.top_controversial(n)

class TestMovieLensAnalysis:
    
    @pytest.fixture
    def mock_movies_csv(self, tmp_path):
        def _create():
            file_path = tmp_path / "movies.csv"
            file_path.write_text(
                "movieId,title,genres\n"
                "1,Toy Story (1995),Adventure|Animation|Children|Comedy|Fantasy\n"
                "2,Jumanji (1995),Adventure|Children|Fantasy\n"
                "3,Grumpier Old Men (1995),Comedy|Romance\n",
                encoding="utf-8"
            )
            return str(file_path)
        return _create()

    @pytest.fixture
    def mock_tags_csv(self, tmp_path):
        def _create():
            file_path = tmp_path / "tags.csv"
            file_path.write_text(
                "userId,movieId,tag,timestamp\n"
                "1,1,funny movie,12345\n"
                "2,1,very long tag with many words,12345\n"
                "3,2,funny,12345\n",
                encoding="utf-8"
            )
            return str(file_path)
        return _create()

    @pytest.fixture
    def mock_ratings_csv(self, tmp_path):
        def _create():
            file_path = tmp_path / "ratings.csv"
            file_path.write_text(
                "userId,movieId,rating,timestamp\n"
                "1,1,4.0,964982703\n"
                "1,2,5.0,964982703\n"
                "2,1,3.0,964982703\n",
                encoding="utf-8"
            )
            return str(file_path)
        return _create()

    @pytest.fixture
    def mock_links_csv(self, tmp_path):
        def _create():
            file_path = tmp_path / "links.csv"
            file_path.write_text(
                "movieId,imdbId,tmdbId\n"
                "1,0114709,862\n"
                "2,0113497,8844\n",
                encoding="utf-8"
            )
            return str(file_path)
        return _create()

    def test_movies_dist_by_release(self, mock_movies_csv):
        try:
            movies = Movies(mock_movies_csv)
            result = movies.dist_by_release()
            
            assert isinstance(result, dict), "Метод должен возвращать словарь"
            
            values = list(result.values())
            assert values == sorted(values, reverse=True), "Данные не отсортированы по убыванию"
            
            for k, v in result.items():
                assert isinstance(k, int), "Год должен быть числом"
                assert isinstance(v, int), "Количество фильмов должно быть числом"
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Необработанное исключение: {e}")

    def test_tags_most_words(self, mock_tags_csv):
        try:
            tags = Tags(mock_tags_csv)
            result = tags.most_words(2)
            
            assert isinstance(result, dict), "Метод должен возвращать словарь"
            
            values = list(result.values())
            assert values == sorted(values, reverse=True), "Сортировка по количеству слов неверна"
            
            for k, v in result.items():
                assert isinstance(k, str), "Тэг должен быть строкой"
                assert isinstance(v, int), "Количество слов должно быть числом"
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Необработанное исключение: {e}")

    def test_ratings_dist_by_year(self, mock_ratings_csv, mock_movies_csv):
        try:
            ratings = Ratings(mock_ratings_csv, mock_movies_csv)
            ratings_movies = ratings.Movies(ratings)
            result = ratings_movies.dist_by_year()
            
            assert isinstance(result, dict), "Метод должен возвращать словарь"
            
            keys = list(result.keys())
            assert keys == sorted(keys), "Сортировка по годам должна быть по возрастанию"
            
            for k, v in result.items():
                assert isinstance(k, int), "Год должен быть целым числом"
                assert isinstance(v, int), "Количество оценок должно быть целым числом"
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Необработанное исключение: {e}")

    def test_links_get_imdb(self, mock_links_csv, mock_movies_csv):
        try:
            links = Links(mock_links_csv, mock_movies_csv, "dummy_api_key")
            
            # Подменяем HTTP-запрос безопасной заглушкой
            def fake_fetch(tmdb_id):
                return {
                    "budget": 1000000,
                    "revenue": 5000000,
                    "runtime": 120,
                    "title": "Mock Title",
                    "credits": {"crew": [{"job": "Director", "name": "John Doe"}]}
                }
            links._fetch_tmdb_movie_details = fake_fetch
            
            result = links.get_imdb([1, 2], ["Director", "Budget"])
            
            assert isinstance(result, list), "Метод должен возвращать список"
            assert all(isinstance(row, list) for row in result), "Элементы должны быть списками"
            
            movie_ids = [row[0] for row in result]
            assert movie_ids == sorted(movie_ids, reverse=True), "Сортировка по movieId должна быть по убыванию"
            
            for row in result:
                assert isinstance(row[0], int), "movieId должен быть числом"
                assert isinstance(row[1], str), "Director должен быть строкой"
                assert isinstance(row[2], int), "Budget должен быть числом"
        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Необработанное исключение: {e}")
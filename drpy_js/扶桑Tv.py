import sys
import re
import requests
import sqlite3
import os
import time
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "WhosTV"

    def init(self, extend=""):
        self.host = "https://whos.tv"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": self.host
        }
        self.db_path = "/storage/emulated/0/私藏视频/whostv.db"
        self._db_info_cache = None

    # ==================== 数据库自动探测（兼容涩库老格式） ====================

    def _get_db_info(self):
        if self._db_info_cache is not None:
            return self._db_info_cache
        if not os.path.exists(self.db_path):
            return None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            target = None
            for t in ["videos", "vod_unified_data", "cj", "vod", "data", "list", "video_detail"]:
                if t in tables:
                    target = t
                    break
            if not target and tables:
                target = tables[0]
            if not target:
                conn.close()
                return None

            cursor.execute(f"PRAGMA table_info(`{target}`)")
            cols = [str(r[1]) for r in cursor.fetchall()]
            conn.close()

            def find_field(candidates):
                for c in candidates:
                    if c in cols:
                        return c
                return None

            mapping = {
                "vod_id": find_field(["id", "vod_id", "uuid", "guid", "vid"]),
                "vod_name": find_field(["name", "vod_name", "title", "subject", "display_name"]),
                "vod_pic": find_field(["image", "vod_pic", "pic", "thumbnail", "img", "cover"]),
                "vod_play_url": find_field(["play_url", "vod_play_url", "url", "link", "m3u8_url"]),
                "vod_remarks": find_field(["vod_remarks", "remarks", "content", "desc", "note"]),
                "type_name": find_field(["type_name", "category_id", "class_name", "cate_name", "actress_id", "tag", "type"]),
                "vod_actor": find_field(["vod_actor", "actor", "actress", "star", "performer", "cast"]),
                "vod_content": find_field(["vod_content", "content", "detail", "intro", "description", "summary"]),
                "update_time": find_field(["update_time", "time", "timestamp", "created_at", "add_time", "utime"])
            }
            self._db_info_cache = {"table": target, "cols": cols, "mapping": mapping}
            return self._db_info_cache
        except:
            return None

    def _db_conn(self):
        try:
            return sqlite3.connect(self.db_path)
        except:
            return None

    def _save_to_db(self, title, pic, play_url, remarks, tags, actors, content):
        if not title:
            return
        info = self._get_db_info()
        if info is None:
            try:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute('''
                    CREATE TABLE IF NOT EXISTS videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vod_name TEXT,
                        vod_pic TEXT,
                        vod_play_url TEXT,
                        vod_remarks TEXT,
                        type_name TEXT,
                        vod_actor TEXT,
                        vod_content TEXT,
                        update_time INTEGER
                    )
                ''')
                conn.commit()
                conn.close()
                self._db_info_cache = None
                info = self._get_db_info()
            except:
                return

        table = info["table"]
        m = info["mapping"]
        name_f = m.get("vod_name")
        if not name_f:
            return

        conn = self._db_conn()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            now = int(time.time())
            one_week = 7 * 24 * 3600
            id_f = m.get("vod_id") or "rowid"
            url_f = m.get("vod_play_url")
            time_f = m.get("update_time")

            sel_cols = f"`{id_f}`"
            if url_f:
                sel_cols += f", `{url_f}`"
            if time_f:
                sel_cols += f", `{time_f}`"
            cursor.execute(f"SELECT {sel_cols} FROM `{table}` WHERE `{name_f}` = ?", (title,))
            row = cursor.fetchone()

            def col_ref(key):
                f = m.get(key)
                return f"`{f}`" if f else None

            if row:
                db_id = row[0]
                db_url = row[1] if len(row) > 1 and url_f else ""
                db_time = row[2] if len(row) > 2 and time_f else 0
                need_update = False
                if url_f and str(db_url or "") != str(play_url or ""):
                    need_update = True
                elif url_f and not db_url:
                    need_update = True
                elif time_f and now - int(db_time or 0) > one_week:
                    need_update = True

                if need_update:
                    sets = []
                    params = []
                    if col_ref("vod_pic"):
                        sets.append(f"{col_ref('vod_pic')} = ?"); params.append(pic)
                    if col_ref("vod_play_url"):
                        sets.append(f"{col_ref('vod_play_url')} = ?"); params.append(play_url)
                    if col_ref("vod_remarks"):
                        sets.append(f"{col_ref('vod_remarks')} = ?"); params.append(remarks)
                    if col_ref("type_name"):
                        sets.append(f"{col_ref('type_name')} = ?"); params.append(tags)
                    if col_ref("vod_actor"):
                        sets.append(f"{col_ref('vod_actor')} = ?"); params.append(actors)
                    if col_ref("vod_content"):
                        sets.append(f"{col_ref('vod_content')} = ?"); params.append(content)
                    if col_ref("update_time"):
                        sets.append(f"{col_ref('update_time')} = ?"); params.append(now)

                    if sets:
                        params.append(db_id)
                        cursor.execute(f"UPDATE `{table}` SET {', '.join(sets)} WHERE `{id_f}` = ?", params)
                        conn.commit()
            else:
                fields = []
                values = []
                if col_ref("vod_name"):
                    fields.append(col_ref("vod_name")); values.append(title)
                if col_ref("vod_pic"):
                    fields.append(col_ref("vod_pic")); values.append(pic)
                if col_ref("vod_play_url"):
                    fields.append(col_ref("vod_play_url")); values.append(play_url)
                if col_ref("vod_remarks"):
                    fields.append(col_ref("vod_remarks")); values.append(remarks)
                if col_ref("type_name"):
                    fields.append(col_ref("type_name")); values.append(tags)
                if col_ref("vod_actor"):
                    fields.append(col_ref("vod_actor")); values.append(actors)
                if col_ref("vod_content"):
                    fields.append(col_ref("vod_content")); values.append(content)
                if col_ref("update_time"):
                    fields.append(col_ref("update_time")); values.append(now)

                if fields:
                    cursor.execute(
                        f"INSERT INTO `{table}` ({', '.join(fields)}) VALUES ({', '.join(['?']*len(values))})",
                        values
                    )
                    conn.commit()
        except:
            pass
        finally:
            conn.close()

    def _get_local_play_url(self, title):
        if not title:
            return None
        info = self._get_db_info()
        if not info:
            return None
        m = info["mapping"]
        name_f = m.get("vod_name")
        url_f = m.get("vod_play_url")
        if not name_f or not url_f:
            return None
        conn = self._db_conn()
        if not conn:
            return None
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT `{url_f}` FROM `{info['table']}` WHERE `{name_f}` = ? AND `{url_f}` IS NOT NULL AND `{url_f}` != ''",
                (title,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except:
            return None
        finally:
            conn.close()

    def _search_local(self, key, limit=20):
        info = self._get_db_info()
        if not info:
            return []
        m = info["mapping"]
        name_f = m.get("vod_name")
        if not name_f:
            return []
        conn = self._db_conn()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            f_id = m.get("vod_id") or "rowid"
            f_pic = m.get("vod_pic") or "''"
            f_rem = m.get("vod_remarks") or "''"
            cursor.execute(
                f"SELECT `{f_id}`, `{name_f}`, `{f_pic}`, `{f_rem}` FROM `{info['table']}` WHERE `{name_f}` LIKE ? LIMIT ?",
                (f"%{key}%", limit)
            )
            videos = []
            for row in cursor.fetchall():
                videos.append({
                    "vod_id": f"local#{row[0]}",
                    "vod_name": str(row[1]),
                    "vod_pic": str(row[2]) if row[2] else "",
                    "vod_remarks": str(row[3]) if row[3] else "本地缓存"
                })
            return videos
        except:
            return []
        finally:
            conn.close()

    # ==================== 在线爬虫 ====================

    def _decode_cover(self, encoded):
        if not encoded:
            return ""
        try:
            key_hex = encoded[-2:]
            key = int(key_hex, 16)
            data_hex = encoded[:-2]
            chars = []
            for i in range(0, len(data_hex), 2):
                byte_val = int(data_hex[i:i+2], 16)
                chars.append(chr(byte_val ^ key))
            return ''.join(chars)
        except:
            return ""

    def _parse_video_list(self, soup):
        videos = []
        items = soup.find_all('a', href=re.compile(r'^/videos/.'))
        for item in items:
            h3 = item.find('h3')
            v_name = h3.get_text(strip=True) if h3 else item.get('alt', '')
            if not v_name:
                continue
            div_cover = item.find('div', attrs={'data-cover-src': True})
            if div_cover:
                encoded = div_cover.get('data-cover-src')
                real_pic = self._decode_cover(encoded)
            else:
                real_pic = ""
            remarks = self.regStr(v_name, r'([A-Z0-9]+-[0-9]+)')
            videos.append({
                "vod_id": item.get('href'),
                "vod_name": v_name,
                "vod_pic": real_pic,
                "vod_remarks": remarks if remarks else ""
            })
        return videos

    def _parse_topic_list(self, soup):
        videos = []
        items = soup.find_all('a', href=re.compile(r'^/topics/.'))
        for item in items:
            img = item.find('img')
            title_tag = item.find('h3') or item.find('h2') or item.find('span', class_=re.compile(r'title|name', re.I))
            name = ""
            if title_tag:
                name = title_tag.get_text(strip=True)
            elif img:
                name = img.get('alt', '').strip()
            href = item.get('href')
            if not name or not href or "page-" in href:
                continue
            pic_url = img.get('src', '') if img else ''
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic_url,
                "vod_remarks": "专题合集",
                "vod_tag": "folder"
            })
        return videos

    # ==================== 核心接口 ====================

    def homeContent(self, filter):
        # 不在分类里添加本地缓存，保持原样
        return {
            'class': [
                {'type_name': '影片库', 'type_id': '/videos'},
                {'type_name': '女优库', 'type_id': '/actresses'},
                {'type_name': '专题', 'type_id': '/topics'}
            ]
        }

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        url = f"{self.host}{tid}"
        if int(pg) > 1:
            url += f"/page-{pg}"

        rsp = self.fetch(url, headers=self.header)
        soup = BeautifulSoup(rsp.text, 'html.parser')
        videos = []

        if tid == "/actresses":
            items = soup.find_all('a', href=re.compile(r'^/actresses/.'))
            for item in items:
                img = item.find('img')
                if not img:
                    continue
                name = img.get('alt', '').strip()
                href = item.get('href')
                if not name or href == "/actresses" or "page-" in href:
                    continue
                pic_url = img.get('src', '')
                count_text = ""
                icon_span = item.find('span', class_=re.compile(r'icon-\[lucide--film\]'))
                if icon_span:
                    parent_flex = icon_span.find_parent('span', class_='flex')
                    if parent_flex:
                        count_text = parent_flex.get_text(strip=True) + "部作品"
                videos.append({
                    "vod_id": href,
                    "vod_name": name,
                    "vod_pic": pic_url,
                    "vod_remarks": count_text if count_text else "作品集",
                    "vod_tag": "folder"
                })

        elif tid == "/topics":
            videos = self._parse_topic_list(soup)
            if not videos:
                videos = self._parse_video_list(soup)

        elif tid.startswith("/topics/"):
            videos = self._parse_video_list(soup)
            h1_tag = soup.find('h1')
            if h1_tag:
                result['type_name'] = h1_tag.get_text(strip=True)

        else:
            videos = self._parse_video_list(soup)

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 999
        result['limit'] = len(videos)
        result['total'] = 9999

        if tid.startswith("/actresses/"):
            h1_tag = soup.find('h1')
            if h1_tag:
                result['type_name'] = h1_tag.get_text(strip=True)
        return result

    def detailContent(self, ids):
        vodId = ids[0]

        if vodId.startswith("/actresses/"):
            return self.categoryContent(vodId, "1", None, None)
        if vodId.startswith("/topics/"):
            return self.categoryContent(vodId, "1", None, None)

        url = self.host + vodId
        rsp = self.fetch(url, headers=self.header)
        soup = BeautifulSoup(rsp.text, 'html.parser')

        title_meta = soup.find('meta', property="og:title")
        title = title_meta.get('content') if title_meta else ""

        pic_meta = soup.find('meta', property="og:image")
        pic = pic_meta.get('content') if pic_meta else ""

        desc = ""
        desc_meta = soup.find('meta', property="og:description")
        if desc_meta:
            desc = desc_meta.get('content', '').strip()
        if not desc:
            desc_tag = soup.find('div', class_=re.compile(r'desc|description|summary|intro|synopsis', re.I))
            if desc_tag:
                desc = desc_tag.get_text(strip=True)
        if not desc:
            detail_section = soup.find('section', class_=re.compile(r'detail|info|about', re.I))
            if detail_section:
                p_tag = detail_section.find('p')
                if p_tag:
                    desc = p_tag.get_text(strip=True)

        source = soup.find('source', type="application/x-mpegURL")
        play_url = source.get('src') if source else ""

        actor_tags = soup.select('a[href^="/actresses/"]')
        actors = ",".join([a.get_text(strip=True) for a in actor_tags if a.get_text(strip=True)])

        tag_tags = soup.select('a[href^="/tags/"] span.truncate')
        tags = ",".join([t.get_text(strip=True) for t in tag_tags])

        # 推荐视频
        recommend_videos = []
        rec_sections = [
            soup.find('section', string=re.compile(r'推荐|相关|Similar|Related|Recommend', re.I)),
            soup.find('div', string=re.compile(r'推荐|相关|Similar|Related|Recommend', re.I)),
            soup.find('h2', string=re.compile(r'推荐|相关|Similar|Related|Recommend', re.I)),
        ]
        rec_container = None
        for sec in rec_sections:
            if sec:
                rec_container = sec.find_parent('section') or sec.find_parent('div')
                if rec_container:
                    break
        if not rec_container:
            rec_container = soup.find('section', class_=re.compile(r'recommend|related|similar', re.I)) \
                or soup.find('div', class_=re.compile(r'recommend|related|similar', re.I))
        if not rec_container:
            all_video_grids = soup.find_all('a', href=re.compile(r'^/videos/.'))
            if len(all_video_grids) > 1:
                first_video = all_video_grids[0]
                rec_items = []
                for item in all_video_grids[1:]:
                    if item.find_parent() != first_video.find_parent():
                        rec_items.append(item)
                all_video_grids = rec_items
            else:
                all_video_grids = []
        else:
            all_video_grids = rec_container.find_all('a', href=re.compile(r'^/videos/.'))

        for item in all_video_grids[:10]:
            h3 = item.find('h3')
            rec_name = h3.get_text(strip=True) if h3 else ""
            if rec_name:
                recommend_videos.append((rec_name, item.get('href', '')))

        # 组装精简简介
        content_parts = []
        if desc:
            content_parts.append(desc)
        if recommend_videos:
            rec_lines = [f"{idx}.{name}" for idx, (name, _) in enumerate(recommend_videos[:6], 1)]
            content_parts.append("📌 " + " ".join(rec_lines))

        vod_content = " | ".join(content_parts) if content_parts else title
        remarks = self.regStr(title, r'([A-Z0-9]+-[0-9]+)') if title else ""

        # 自动保存到本地数据库（浏览时触发）
        self._save_to_db(title, pic, play_url, remarks, tags, actors, vod_content)

        # ========== 播放线路：合并为单线路多选集（图2效果） ==========
        episodes = []

        # 在线源
        if play_url and str(play_url).startswith('http'):
            episodes.append("全高清$" + str(play_url))

        # 本地源
        local_url = self._get_local_play_url(title)
        if local_url and str(local_url).startswith('http'):
            episodes.append("本地高清$" + str(local_url))

        # 保底处理，防止TVBox解析空数组
        if episodes:
            play_from = ["在线观看"]
            play_url_parts = ["#".join(episodes)]
        else:
            play_from = ["暂无源"]
            play_url_parts = ["未获取$http://127.0.0.1/empty.m3u8"]

        vod = {
            "vod_id": vodId,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": tags,
            "vod_actor": actors,
            "vod_content": vod_content,
            "vod_play_from": "$$".join(play_from),
            "vod_play_url": "$$".join(play_url_parts)
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        # TVBox框架传入的id可能是"集名$URL"或纯URL，统一提取真实URL
        real_url = str(id)
        if '$' in real_url:
            real_url = real_url.split('$', 1)[-1]
        return {
            "parse": 0,
            "url": real_url,
            "header": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://whos.tv/",
                "Origin": "https://whos.tv"
            }
        }

    def searchContent(self, key, quick):
        url = f"{self.host}/result?serach={key}"
        rsp = self.fetch(url, headers=self.header)
        soup = BeautifulSoup(rsp.text, 'html.parser')
        online_videos = self._parse_video_list(soup)
        local_videos = self._search_local(key)
        all_videos = online_videos + local_videos
        return {"list": all_videos}

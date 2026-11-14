from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QLocale
from fontTools.ttLib import TTFont
from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication, QFontMetrics, QFontInfo


#Data class holding font data
@dataclass(frozen=True) #Static
class FontMetadata:
    family: str
    style: str
    weight: int | None
    unicode_codepoint_count: int
    variable_axes: dict[str, tuple[float, float, float]] # min, default, max for weight of font

@dataclass(frozen=True)
class RegisteredFont:
    font_id: int # Unique identifier for used font, only for Qt
    path: Path
    families: tuple[str, ...]
    metadata: FontMetadata

# Functions for font management
class FontManager:
    EXTENSIONS = {".ttf", ".otf"} #allowed file format
    WEIGHTS = {100, 200, 300, 400, 500, 600, 700, 800, 900}

    # supported language
    SCRIPT_MAP = {
        QLocale.Script.TraditionalChineseScript: QFontDatabase.WritingSystem.TraditionalChinese,
        QLocale.Script.SimplifiedChineseScript: QFontDatabase.WritingSystem.SimplifiedChinese,
        QLocale.Script.LatinScript: QFontDatabase.WritingSystem.Latin
    }

    def __init__(self, font_dir: str | Path | None = None):
        self.font_dir = Path(font_dir or  Path(__file__).resolve().parent / "custom_fonts").expanduser().resolve()

        #Find font
        self.path_identifier: dict[Path, RegisteredFont] = {}
        self.id_identifier: dict[int, RegisteredFont] = {}
        #What range of character it supports
        self.char_coverage: dict[int, frozenset[int]] = {}
        #Alternative names allowed
        self.aliases: dict[str, str] = {}
        self.family_identifier: dict[str, list[RegisteredFont]] = {}

    @staticmethod
    #Check if GUI is available
    def require_qt() -> None:
        if not isinstance(QGuiApplication.instance(), QGuiApplication):
            raise RuntimeError(
                "Create QGuiApplication(sys.argv) before using Qt font operations."
            )

    #Check whether path exist
    def resolve_path(self, font_path: str | Path) -> Path:
        #Convert path without placeholder reference
        path = Path(font_path).expanduser()

        if not path.is_absolute() and not path.is_file():
            path = self.font_dir / path

        #Convert to absolute --> reproducible by others
        path = path.resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Font file not found: {path}")
        if path.suffix.lower() not in self.EXTENSIONS:
            raise ValueError(f"Expected a .ttf or .otf file: {path}")
        return path

    #Return metadata and coverage for the font
    @staticmethod
    def read_font(path: Path) -> tuple[FontMetadata, frozenset[int]]:
        font = TTFont(str(path), lazy=True)
        try:
            name = font["name"]

            family = name.getDebugName(16) or name.getDebugName(1) or path.stem #Font file name or metadata name
            style = name.getDebugName(17) or name.getDebugName(2) or "Regular" #Provide fallback
            weight = int(font["OS/2"].usWeightClass) if "OS/2" in font else None
            cmap = font.getBestCmap()

            if cmap is None:
                raise ValueError(f"Font has no Unicode cmap: {path}")

            axes: dict[str, tuple[float, float, float]] = {}
            if "fvar" in font:
                for axis in font["fvar"].axes:
                    axes[axis.axisTag] = (
                        float(axis.minValue),
                        float(axis.defaultValue),
                        float(axis.maxValue),
                    )

            metadata = FontMetadata(
                family=family,
                style=style,
                weight=weight,
                unicode_codepoint_count=len(cmap),
                variable_axes=axes,
            )

        finally:
            font.close()

        return metadata, frozenset(cmap)

    def inspect_font(self, font_path: str | Path) -> FontMetadata:
        #Read fontTools metadata without registering a font with Qt.
        path = self.resolve_path(font_path)
        record = self.path_identifier.get(path)
        if record:
            return record.metadata
        metadata, _ = self.read_font(path)
        return metadata

    def register_font(self, font_path: str | Path) -> RegisteredFont:
        #Register a custom font exactly once per FontManager instance.
        self.require_qt()
        path = self.resolve_path(font_path)

        #Return font if it exists
        if path in self.path_identifier:
            return self.path_identifier[path]

        metadata, codepoints = self.read_font(path)
        font_id = QFontDatabase.addApplicationFont(str(path))

        #Fail to load
        if font_id == -1:
            raise RuntimeError(f"Qt failed to load font: {path}")

        families = tuple(QFontDatabase.applicationFontFamilies(font_id))
        if not families:
            #Font doesnt contain family name
            QFontDatabase.removeApplicationFont(font_id)
            raise RuntimeError(f"Qt reported no family names for: {path}")

        record = RegisteredFont(font_id=font_id, path=path, families=families, metadata=metadata)
        self.path_identifier[path] = record
        self.id_identifier[font_id] = record
        self.char_coverage[font_id] = codepoints

        for family in record.families:
            key = family.casefold()

            self.family_identifier.setdefault(key, []).append(record)

        return record

    def register_directory(self) -> list[RegisteredFont]:
        #Register every .ttf and .otf file in custom_fonts directory
        self.require_qt()

        if not self.font_dir.is_dir():
            raise FileNotFoundError(f"Font directory not found: {self.font_dir}")

        #look for all ttf or otf file including subdirectories, add to a list.
        paths = sorted(path for path in self.font_dir.rglob("*") if path.is_file() and path.suffix.lower() in self.EXTENSIONS)

        return [self.register_font(path) for path in paths]

    def missing_characters(self, font_id: int, text: str) -> list[str]:
        """Return unique codepoints absent from a registered font's Unicode cmap.
        This is a coverage check, not a guarantee of correct complex-script shaping.
        """

        if font_id not in self.char_coverage:
            raise KeyError(f"Unknown registered font ID: {font_id}")

        codepoints = self.char_coverage[font_id]
        ignored_controls = "\n\r\t"

        return list(dict.fromkeys(char for char in text if char not in ignored_controls and ord(char) not in codepoints))

    def supports_text(self, font_id: int, text: str) -> bool:
        return not self.missing_characters(font_id, text)

    def add_alias(self, configured_family: str, actual_family: str) -> None:
        """Explicitly map a YAML family label to a Qt-visible family name."""
        self.require_qt()
        available = {name.casefold(): name for name in QFontDatabase.families()}

        target = available.get(actual_family.casefold())
        if target is None:
            raise ValueError(f"Cannot alias unavailable family: {actual_family}")
        self.aliases[configured_family.casefold()] = target

    def find_registered_font(self, family: str, weight: int = 400) -> RegisteredFont:
        target = self.aliases.get(family.casefold(), family)
        matched_fonts = self.family_identifier.get(target.casefold(), [])

        if not matched_fonts:
            raise ValueError(f"Cannot find font for family: {family}")

        return min(matched_fonts,key=lambda record: abs((record.metadata.weight or 400) - weight))

    def resolve_language_support(self, family: str, language: str, font: QFont, font_id: int = None) -> None:
        local_lang = QLocale(language)
        script = local_lang.script()

        target_system = self.SCRIPT_MAP.get(script)
        if target_system is not None:
            #family based check
            supported_systems = QFontDatabase.writingSystems(family)
            if target_system not in supported_systems:
                raise ValueError(f"The font family {family} does not support {language}")

        sample_chars = ""
        if script == QLocale.Script.LatinScript:
            sample_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        elif script == QLocale.Script.TraditionalChineseScript:
            sample_chars = "繁體國灣語"
        elif script == QLocale.Script.SimplifiedChineseScript:
            sample_chars = "简体国湾语"

        if not sample_chars:
            return

        if font_id is not None:
            is_supported = self.supports_text(font_id, sample_chars)
        else:
            fm = QFontMetrics(font)
            is_supported = all(fm.inFont(ch) for ch in sample_chars)

        if not is_supported:
            raise ValueError(
                f"Font family '{family}' is missing required glyphs for '{language}'."
            )

    #See if the font support a language
    def resolve_font(self, family: str, weight: int = 400, pixel_size: int | None = None, language: str | list[str] | None = None,
                     font_id: int | None = None) -> QFont:
        """Return a Qt font, rejecting an unavailable family instead of silently
        accepting Qt substitution. `

        For a system-installed family, use Qt to resolve it. Coverage validation
        currently works only with registered local font files.
        """
        self.require_qt()

        if weight not in self.WEIGHTS:
            raise ValueError("weight must be 100, 200, ..., 900 in current version")

        if pixel_size is not None and pixel_size <= 0:
            raise ValueError("pixel_size must be positive")

        requested = self.aliases.get(family.casefold(), family)
        available = {name.casefold(): name for name in QFontDatabase.families()}

        actual = available.get(requested.casefold())
        if actual is None:
            raise ValueError(
                f"Font family '{family}' not found. Register its font file or "
                "check the YAML name against Qt's reported families."
            )

        font = QFont(actual)
        if language is not None:
            languages = [language] if isinstance(language, str) else language

            for lang in languages:
                self.resolve_language_support(actual, lang, font, font_id=font_id)

        font.setWeight(QFont.Weight(weight))
        if pixel_size is not None:
            font.setPixelSize(pixel_size)

        return font

    #Direct reference
    def resolve_registered_font(self, font_id: int, weight: int = 400,
            pixel_size: int | None = None, text: str | None = None, language: str | list[str] | None = None) -> QFont:

        record = self.id_identifier.get(font_id)
        if record is None:
            raise ValueError(f"Font ID {font_id} is not registered")

        if text is not None:
            missing = self.missing_characters(font_id, text)

            if missing:
                raise ValueError(f"Unsupported characters: {missing}")

        family = record.families[0]

        font = self.resolve_font(
            family=family,
            weight=weight,
            pixel_size=pixel_size,
            language=language if text is None else None,
            font_id=font_id
        )

        matched = QFontInfo(font).family()

        if matched.casefold() != family.casefold():
            raise RuntimeError(
                f"Font substitution detected: "
                f"{family} -> {matched}"
            )

        return font

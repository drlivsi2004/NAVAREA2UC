"""Build the compact Black Sea ECDIS semantics proof export.

The demo deliberately uses the production modern Furuno exporter so the
checked-in XML is an example of the same UserChart v1.3 shape used by the
application, not a hand-written mock. All demo coordinates are in open water
south of Odesa in the north-western Black Sea.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import (  # noqa: E402
    add_area,
    add_circle,
    add_label,
    add_line,
    create_area,
    create_circle,
    create_container,
    create_label,
    create_line,
    create_message,
    export_furuno_modern,
)


DEMO_NAV_ID = "DEMO"
DEMO_MESSAGE_ID = "NAVAREA DEMO 1/2026"
OUTPUT_PATH = Path(__file__).with_name("NAVAREA2UC_ECDIS_SEMANTICS_DEMO.xml")


def _add_demo_label(container, message, *, text, description, coord, color, danger, style=4):
    label = create_label(
        style=style,
        color=color,
        check_danger=danger,
        text=text,
        description=description,
        coord=coord,
    )
    add_label(label, container, message)


def build_demo_container():
    """Return one small, self-contained scene containing every demo class."""

    container = create_container(DEMO_NAV_ID)
    message = create_message(DEMO_MESSAGE_ID)
    container["messages"].append(message)

    # Route, survey, iceberg and leading-light lines all use the production
    # line export path. The scene is intentionally fictional and compact.
    add_line(
        create_line(
            name="LINE - RECOMMENDED ROUTE",
            description="LINE | route",
            coords=[
                (45.700000, 30.950000),
                (45.820000, 31.120000),
                (45.960000, 31.340000),
                (46.100000, 31.560000),
            ],
            color="CHYLW",
            check_danger=0,
        ),
        container,
        message,
    )

    add_line(
        create_line(
            name="LINE - SURVEY TRACK",
            description="LINE | survey",
            coords=[
                (45.740000, 31.700000),
                (45.860000, 31.540000),
                (45.980000, 31.360000),
            ],
            color="NINFO",
            check_danger=0,
        ),
        container,
        message,
    )

    add_line(
        create_line(
            name="LINE - ICEBERG TRACKLINE",
            description="LINE | iceberg trackline | DANGER=YES",
            coords=[
                (46.180000, 31.000000),
                (46.100000, 31.200000),
                (46.020000, 31.400000),
                (45.940000, 31.620000),
            ],
            color="CHRED",
            check_danger=1,
        ),
        container,
        message,
    )

    add_line(
        create_line(
            name="LINE - LEADING LIGHTS",
            description="LINE | leading lights",
            coords=[
                (45.720000, 31.740000),
                (45.820000, 31.740000),
            ],
            color="CHYLW",
            check_danger=0,
        ),
        container,
        message,
    )

    add_area(
        create_area(
            name="AREA - RESTRICTED DANGER ZONE",
            description="AREA | restricted zone | DANGER=YES",
            coords=[
                (45.820000, 31.150000),
                (45.820000, 31.380000),
                (45.980000, 31.380000),
                (45.980000, 31.150000),
            ],
            color="CHRED",
            check_danger=1,
        ),
        container,
        message,
    )

    add_area(
        create_area(
            name="AREA - SPECIAL SURVEY ZONE",
            description="AREA | survey zone",
            coords=[
                (45.660000, 31.450000),
                (45.660000, 31.720000),
                (45.760000, 31.720000),
                (45.760000, 31.450000),
            ],
            color="NINFO",
            check_danger=0,
        ),
        container,
        message,
    )

    add_area(
        create_area(
            name="AREA - FIRING EXERCISE DANGER ZONE",
            description="AREA | firing exercise | DANGER=YES",
            coords=[
                (46.020000, 31.160000),
                (46.020000, 31.400000),
                (46.180000, 31.400000),
                (46.180000, 31.160000),
            ],
            color="CHRED",
            check_danger=1,
        ),
        container,
        message,
    )

    add_circle(
        create_circle(
            name="CIRCLE - EXPLOSIVES DUMPING GROUND",
            description="CIRCLE | explosives area | radius=3 NM | DANGER=YES",
            coord=(46.000000, 31.700000),
            range_val=3.0,
            color="CHRED",
            check_danger=1,
        ),
        container,
        message,
    )

    _add_demo_label(
        container,
        message,
        text="SPECIAL MARK BUOY - YELLOW",
        description="POINT | special mark buoy | yellow class | DANGER=NO",
        coord=(45.880000, 31.300000),
        color="CHYLW",
        danger=0,
    )
    _add_demo_label(
        container,
        message,
        text="ISOLATED DANGER BUOY",
        description="POINT | isolated danger buoy | DANGER=YES",
        coord=(45.920000, 31.380000),
        color="CHRED",
        danger=1,
    )
    _add_demo_label(
        container,
        message,
        text="DEGRADED BUOY",
        description="POINT | degraded buoy | STATUS=DEGRADED",
        coord=(45.840000, 31.240000),
        color="NINFO",
        danger=0,
    )
    _add_demo_label(
        container,
        message,
        text="OFFSHORE PLATFORM",
        description="POINT | offshore platform",
        coord=(45.780000, 31.680000),
        color="RESBL",
        danger=0,
        style=5,
    )
    _add_demo_label(
        container,
        message,
        text="WRECK - DANGER POINT",
        description="POINT | wreck | DANGER=YES",
        coord=(45.960000, 31.420000),
        color="CHRED",
        danger=1,
        style=3,
    )
    _add_demo_label(
        container,
        message,
        text="SECURITY INCIDENT",
        description="POINT | security incident | DANGER=YES",
        coord=(46.040000, 31.000000),
        color="CHRED",
        danger=1,
        style=5,
    )
    _add_demo_label(
        container,
        message,
        text="ICEBERG TRACKLINE",
        description="POINT | iceberg trackline marker | DANGER=YES",
        coord=(46.020000, 31.400000),
        color="CHRED",
        danger=1,
        style=6,
    )
    _add_demo_label(
        container,
        message,
        text="LIGHTHOUSE",
        description="POINT | lighthouse | fixed light",
        coord=(45.720000, 31.740000),
        color="CHYLW",
        danger=0,
        style=2,
    )
    _add_demo_label(
        container,
        message,
        text="LEADING LIGHT - FRONT",
        description="POINT | leading light | front",
        coord=(45.760000, 31.740000),
        color="CHYLW",
        danger=0,
        style=2,
    )
    _add_demo_label(
        container,
        message,
        text="LEADING LIGHT - REAR",
        description="POINT | leading light | rear",
        coord=(45.820000, 31.740000),
        color="CHYLW",
        danger=0,
        style=2,
    )
    _add_demo_label(
        container,
        message,
        text="DRIFTING OBJECTS - DANGER",
        description="POINT | drifting objects | DANGER=YES",
        coord=(45.980000, 31.720000),
        color="CHRED",
        danger=1,
        style=3,
    )
    _add_demo_label(
        container,
        message,
        text="FIRING EXERCISE",
        description="POINT | firing exercise marker | DANGER=YES",
        coord=(46.100000, 31.280000),
        color="CHRED",
        danger=1,
        style=6,
    )
    _add_demo_label(
        container,
        message,
        text="ECDIS SEMANTICS DEMO",
        description="PROOF SCENE | four geometry groups",
        coord=(45.680000, 31.780000),
        color="NINFO",
        danger=0,
        style=2,
    )

    return container


def render_demo_xml():
    return export_furuno_modern(DEMO_NAV_ID, build_demo_container()) + "\n"


def write_demo_xml(output_path=OUTPUT_PATH):
    output_path = Path(output_path)
    output_path.write_text(render_demo_xml(), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = write_demo_xml()
    print(f"Wrote {path}")
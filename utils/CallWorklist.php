{PHP}
$HOST = "192.168.1.122";
$PORT = "8090";
$AUTH = "Basic aGFydGlnOmhhcnRpZw==";
$name = urlencode(utf8_encode("{Patient.Stammdaten.Nachname}"));
$surname = urlencode(utf8_encode("{Patient.Stammdaten.Vorname}"));
$birthdate = urlencode("{Patient.Stammdaten.Geburtsdatum}");
$arztname = "{AArzt.Nachname}";
$arztvorname = "{AArzt.Vorname}";
$arzt = urlencode(utf8_encode("$arztname^$arztvorname"));
$sex = urlencode("{Patient.Geschlecht}");
$id = urlencode("{Patient.PatID}");
$procedure = urlencode(utf8_encode("Abdomen"));

$contents = file_get_contents("http://$HOST:$PORT/worklist/add?id=$id&name=$name&surname=$surname&birthdate=$birthdate&sex=$sex&procedure=$procedure&physician=$arzt");
{/PHP}

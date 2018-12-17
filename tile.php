<?php
include "config.php";

function dieWith($message){
    header("Content-Type: text/plain; charset=UTF-8;");
    echo $message."\n";
    die();
}

if (!array_key_exists("x", $_GET) || 
    !array_key_exists("y", $_GET) ||
    !array_key_exists("z", $_GET)) {
 
    dieWith("Some argument missing!");
}

$x=intval($_GET["x"]);
$y=intval($_GET["y"]);
$z=intval($_GET["z"]);
$debug=array_key_exists("debug", $_GET) && $enableDebug;

if ($z < 0 || $z > $maximumZoomLevel){
    dieWith("Zoom out of range!");
}

function execAndCheck($cmd){
  exec($cmd, $output, $code);
  global $debug;
  if ($debug){
    echo "command: \n$cmd\n";
    echo "exited with $code\n";
    print_r($output);
  } else if ($code != 0) {
    echo "command: \n$cmd\n";
    echo "exited with $code\n";
    print_r($output);
    dieWith("Process failed");
  }
}

function sendTile($tileFile){
  header("Content-Type: image/png");
  header("Expires: ".GMDate("D, d M Y H:i:s", time() + $tileCacheExpiration)." GMT");
  readfile($tileFile);
}

$worldRes = pow(2.0, $z);

if ($x < 0 || $y < 0 || $x >= $worldRes || $y >= $worldRes){
    dieWith("Coords out of range!");
}

$tileFile = "$tileCacheDir/$z/$x/$y.png";

if (is_file($tileFile) && !$debug){
  sendTile($tileFile);
  exit(0);
}
if ($z < $minimumZoomLevel){
  sendTile("empty.png");
  exit(0);
}

if ($debug){
  header("Content-Type: text/plain; charset=UTF-8;");
}

$subdir = dirname($tileFile);
if (!is_dir($subdir)){
  if (!mkdir($subdir, /*mode*/ 0777, /*recursive*/ true) && (!is_dir($subdir))){
    header("500 Internal Server Error");
    die("Cache directory creation fails.");
  }
}

execAndCheck("python3 $scriptDir/hillshade.py \"$demDataFile\" \"$tileFile\" $z $x $y");

if ($debug){
  echo "$tileFile\n";
}else {
  sendTile($tileFile);
}

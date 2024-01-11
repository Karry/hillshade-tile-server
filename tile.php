<?php
include "config.php";

// BSD 3-Clause License
//
// Copyright (c) 2018, Lukáš Karas
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
// * Redistributions of source code must retain the above copyright notice, this
//   list of conditions and the following disclaimer.
//
// * Redistributions in binary form must reproduce the above copyright notice,
//   this list of conditions and the following disclaimer in the documentation
//   and/or other materials provided with the distribution.
//
// * Neither the name of the copyright holder nor the names of its
//   contributors may be used to endorse or promote products derived from
//   this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

function dieWith($message){
    header($_SERVER['SERVER_PROTOCOL']." 500 Internal Server Error");
    header("Content-Type: text/plain; charset=UTF-8;");
    echo $message."\n";
    die();
}

function dieWithFalse($res) {
    if ($res === false){
        dieWith("Memcached operation failed.");
    }
    return $res;
}
function loadOrDie($extension){
  if (!extension_loaded($extension)){
    if (!(function_exists("dl") && dl($extension))){
      header("Content-Type: text/plain; charset=UTF-8;");
      echo "Can't load php extension ".$extension."\n";
      die();
    }
  }
}
loadOrDie("memcached");
loadOrDie("memcache");

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
  $time_start = microtime(true);
  exec($cmd, $output, $code);
  $time_end = microtime(true);

  global $debug;
  if ($debug){
    echo "command: \n$cmd\n";
    $time = $time_end - $time_start;
    echo "exited with $code after $time seconds\n";
    print_r($output);
  } else if ($code != 0) {
    echo "command: \n$cmd\n";
    echo "exited with $code\n";
    print_r($output);
    dieWith("Process failed");
  }
}

function sendTile($tileFile){
  global $tileCacheExpiration;
  header("Content-Type: image/png");
  header("Expires: ".GMDate("D, d M Y H:i:s", time() + $tileCacheExpiration)." GMT");
  header("Cache-Control: max-age=" . $tileCacheExpiration);
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
    dieWith("Cache directory creation fails.");
  }
}

$demDataFile = "";
foreach ($demDataFiles as $zoom => $value) {
    if ($z <= $zoom){
        $demDataFile = $value;
        break;
    }
}

if ($demDataFile == ""){
    dieWith("Can't determine data file");
}

$memcache=new Memcache();
if (!$memcache->connect('127.0.0.1', 11211)){
  dieWith("Can't connect to memcached.");
}

// https://www.leaseweb.com/labs/2015/06/limit-concurrent-php-requests-using-memcache/
function limit_concurrency($concurrency,$spinLock,$interval,$key){
  global $debug;
  global $memcache;
  $start = microtime(true);

  $memcache->add($key,0,false);
  while (dieWithFalse($memcache->increment($key)) > $concurrency) {
    dieWithFalse($memcache->decrement($key));
    if (!$spinLock || microtime(true)-$start>$interval) {
      //http_response_code(429);
      header($_SERVER['SERVER_PROTOCOL']." 429 Too Many Requests");
      die('429: Too Many Requests');
    }
    usleep($spinLock*1000000);
  }
  register_shutdown_function(function() use ($memcache,$key){ $memcache->decrement($key); });
  if ($debug){
    echo "memcache $key: " . $memcache->get($key) . "\n";
  }
}
limit_concurrency($maxConcurency, 0.15, $spinLockInterval, 'hillshade_concurrency');

execAndCheck("python3 $scriptDir/hillshade.py \"$demDataFile\" \"$tileFile\" $z $x $y");

if ($debug){
  echo "$tileFile\n";
}else {
  sendTile($tileFile);
}

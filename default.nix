{ pkgs ? import <nixpkgs> {} }:

let
  poetry2nix = import (pkgs.fetchFromGitHub {
    owner = "nix-community";
    repo = "poetry2nix";
    rev = "2024.10.2267247";  # Using a specific version instead of master
    sha256 = "sha256-NEagK4dENd9Riu8Gc1JHOnrKL/3TmiAINDCAvXqWkL4=";
  }) {
    inherit pkgs;
  };
in
{
  package = poetry2nix.mkPoetryApplication {
    projectDir = ./.;
  };
}

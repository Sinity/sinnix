cmake_minimum_required(VERSION 3.21)
project(sinnix_rank_desktop LANGUAGES CXX)
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

find_package(Qt6 REQUIRED COMPONENTS Core Gui OpenGL Qml Quick)
find_package(PkgConfig REQUIRED)
pkg_check_modules(MPV REQUIRED IMPORTED_TARGET mpv)

qt_standard_project_setup(REQUIRES 6.8)
qt_add_library(sinnix_video SHARED)
qt_add_qml_module(sinnix_video
    URI Sinnix.Video
    VERSION 1.0
    OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/Sinnix/Video
    SOURCES mpvoutput.cpp mpvoutput.h
)
target_compile_features(sinnix_video PRIVATE cxx_std_17)
target_link_libraries(sinnix_video PRIVATE Qt6::OpenGL Qt6::Quick PkgConfig::MPV)
set_target_properties(sinnix_videoplugin PROPERTIES INSTALL_RPATH "$ORIGIN/../../../..")

install(TARGETS sinnix_video LIBRARY DESTINATION lib)
install(TARGETS sinnix_videoplugin LIBRARY DESTINATION lib/qt-6/qml/Sinnix/Video)
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/Sinnix/Video/qmldir
    ${CMAKE_CURRENT_BINARY_DIR}/Sinnix/Video/sinnix_video.qmltypes
    DESTINATION lib/qt-6/qml/Sinnix/Video
)
